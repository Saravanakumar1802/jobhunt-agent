"""Model health + free replacement suggestions for the Models page.

Availability is checked against each provider's *model list* endpoint, which
costs zero tokens. A model missing from that list has been retired or renamed.
The "Test" button sends one real tiny completion when you want certainty.
"""

import asyncio
import logging

import httpx

from app.services.llm.client import LLMClient, classify_error, provider_key
from app.services.llm.free_guard import is_free, provider_of

log = logging.getLogger(__name__)

GROQ_MODELS = "https://api.groq.com/openai/v1/models"
GEMINI_MODELS = "https://generativelanguage.googleapis.com/v1beta/models"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


async def _groq(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(GROQ_MODELS, headers={"Authorization": f"Bearer {provider_key('groq')}"})
    r.raise_for_status()
    return [f"groq/{m['id']}" for m in r.json().get("data", []) if m.get("active", True)]


async def _gemini(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(GEMINI_MODELS, params={"key": provider_key("gemini"), "pageSize": 1000})
    r.raise_for_status()
    return [
        "gemini/" + m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


async def _openrouter(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(OPENROUTER_MODELS)
    r.raise_for_status()
    out = []
    for m in r.json().get("data", []):
        pricing = m.get("pricing") or {}
        if m.get("id", "").endswith(":free") and str(pricing.get("prompt", "0")) in ("0", "0.0"):
            out.append(f"openrouter/{m['id']}")
    return out


FETCHERS = {"groq": _groq, "gemini": _gemini, "openrouter": _openrouter}


async def fetch_available(client: httpx.AsyncClient, providers: list[str]) -> dict[str, list[str] | None]:
    """{provider: [free litellm model ids]} — None when the list could not be fetched."""

    async def one(p: str):
        try:
            return p, sorted(m for m in await FETCHERS[p](client) if is_free(m))
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("Could not list %s models: %s", p, exc)
            return p, None

    return dict(await asyncio.gather(*(one(p) for p in providers)))


async def check_all(llm: LLMClient, client: httpx.AsyncClient) -> dict:
    """Refresh health for every model in the chains; return the full report."""
    available = await fetch_available(client, llm.configured_providers())
    for model in llm.all_models():
        provider = provider_of(model)
        listed = available.get(provider)
        if not provider_key(provider) or listed is None:
            continue  # no key / list unavailable → keep previous status
        if model in listed:
            if llm.health.get(model, {}).get("status") not in ("ok",):
                await llm.mark(model, "ok", "listed by provider")
        else:
            await llm.mark(model, "unavailable", "Not offered by the provider any more (retired or renamed)")
    return report(llm, available)


def report(llm: LLMClient, available: dict | None = None) -> dict:
    tiers = {
        tier: [
            {"model": m, "provider": provider_of(m), "status": llm.status_of(m),
             "detail": llm.health.get(m, {}).get("detail", ""), "checked_at": llm.health.get(m, {}).get("checked_at")}
            for m in llm.chains[tier]
        ]
        for tier in llm.chains
    }
    return {
        "tiers": tiers,
        "tier_ok": {t: llm.tier_available(t) for t in llm.chains},
        "providers": {p: bool(provider_key(p)) for p in ("groq", "gemini", "openrouter")},
        "suggestions": {p: (v or [])[:60] for p, v in (available or {}).items()},
        "last_model": llm.last_model,
    }


async def ping(llm: LLMClient, model: str) -> dict:
    """One real, tiny completion against a single model."""
    import litellm

    try:
        await litellm.acompletion(
            model=model, messages=[{"role": "user", "content": "Reply with: ok"}], max_tokens=20,
            api_key=provider_key(provider_of(model)), timeout=20, num_retries=0,
            **({"reasoning_effort": "low"} if "gpt-oss" in model else {}),
        )
    except Exception as exc:  # noqa: BLE001
        status = classify_error(exc)
        await llm.mark(model, "ok" if status == "rate_limited" else status, str(exc))
        return {"model": model, "status": status, "detail": str(exc)[:300]}
    await llm.mark(model, "ok", "test call succeeded")
    return {"model": model, "status": "ok", "detail": "test call succeeded"}
