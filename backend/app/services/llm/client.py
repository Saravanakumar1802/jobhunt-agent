"""Priority fallback over free LLM providers, built on LiteLLM's unified API.

Why not LiteLLM's Router? We need (1) a strict, user-editable priority order,
(2) a visible health state per model for the UI, and (3) a free-only guard.
A small explicit loop gives all three and is easy to test:

    for model in chain[tier]:
        skip if no key / marked unavailable / cooling down after a 429
        try call → success: log tokens, return
        429            → cool down N seconds, try next
        retired/404    → mark "unavailable" (shown in UI), try next
        other errors   → try next
    all failed → LLMUnavailableError
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import litellm

from app.core.config import DEFAULT_MID_MODELS, DEFAULT_SMALL_MODELS, get_settings
from app.core.errors import LLMUnavailableError
from app.core.utils import utcnow
from app.services.llm.free_guard import is_free, provider_of

log = logging.getLogger(__name__)
litellm.drop_params = True          # silently drop params a provider doesn't support
litellm.suppress_debug_info = True

TIERS = ("small", "mid")
RETIRED_HINTS = ("decommission", "deprecated", "does not exist", "not found", "no longer", "unknown model",
                 "model_not_found", "invalid model", "not supported")


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


def provider_key(provider: str) -> str:
    s = get_settings()
    return {"groq": s.groq_api_key, "gemini": s.gemini_api_key, "openrouter": s.openrouter_api_key}.get(provider, "")


def classify_error(exc: Exception) -> str:
    """Map a LiteLLM exception to a health status."""
    msg = str(exc).lower()
    if isinstance(exc, litellm.RateLimitError) or "rate limit" in msg or "quota" in msg or "429" in msg:
        return "rate_limited"
    if isinstance(exc, litellm.AuthenticationError):
        return "auth_error"
    if isinstance(exc, litellm.NotFoundError) or any(h in msg for h in RETIRED_HINTS):
        return "unavailable"
    return "error"


class LLMClient:
    def __init__(self, settings_repo=None, usage_repo=None):
        self.settings_repo = settings_repo
        self.usage_repo = usage_repo
        self.chains: dict[str, list[str]] = {"small": list(DEFAULT_SMALL_MODELS), "mid": list(DEFAULT_MID_MODELS)}
        self.health: dict[str, dict] = {}
        self._cooldown_until: dict[str, float] = {}
        self._sem = asyncio.Semaphore(get_settings().llm_concurrency)
        self.last_model: str | None = None

    # --- configuration ----------------------------------------------------------
    async def load(self) -> None:
        """Apply model chains saved from the UI and the last known health."""
        if not self.settings_repo:
            return
        if saved := await self.settings_repo.get_models():
            for tier in TIERS:
                models = [m for m in saved.get(tier, []) if is_free(m)]
                if models:
                    self.chains[tier] = models
        self.health.update(await self.settings_repo.get_health())

    async def set_chains(self, small: list[str], mid: list[str], user_id: str) -> None:
        self.chains = {"small": small, "mid": mid}
        for m in {*small, *mid}:
            self.health.pop(m, None)  # re-evaluate on next use / check
        if self.settings_repo:
            await self.settings_repo.save_models(small, mid, user_id)

    def all_models(self) -> list[str]:
        return list(dict.fromkeys(self.chains["small"] + self.chains["mid"]))

    def configured_providers(self) -> list[str]:
        return [p for p in ("groq", "gemini", "openrouter") if provider_key(p)]

    # --- health -------------------------------------------------------------------
    async def mark(self, model: str, status: str, detail: str = "") -> None:
        prev = self.health.get(model, {}).get("status")
        self.health[model] = {"status": status, "detail": detail[:300], "checked_at": utcnow().isoformat()}
        if self.settings_repo and prev != status:
            await self.settings_repo.save_health(self.health)

    def status_of(self, model: str) -> str:
        if not provider_key(provider_of(model)):
            return "no_key"
        if self._cooldown_until.get(model, 0) > time.monotonic():
            return "rate_limited"
        return self.health.get(model, {}).get("status", "unknown")

    def tier_available(self, tier: str) -> bool:
        return any(self.status_of(m) in ("ok", "unknown") for m in self.chains[tier])

    # --- calls ----------------------------------------------------------------------
    async def complete(self, tier: str, messages: list[dict], *, max_tokens: int, json_mode: bool = True,
                       temperature: float = 0.0, node: str = "") -> LLMResponse:
        s = get_settings()
        errors: list[str] = []
        for model in self.chains[tier]:
            status = self.status_of(model)
            if status in ("no_key", "unavailable", "rate_limited", "auth_error"):
                errors.append(f"{model}: {status}")
                continue
            kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                      "api_key": provider_key(provider_of(model)), "timeout": s.llm_timeout_seconds,
                      "num_retries": 0}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            if "gpt-oss" in model:
                kwargs["reasoning_effort"] = "low"  # reasoning tokens count against max_tokens
            started = time.perf_counter()
            try:
                async with self._sem:
                    resp = await litellm.acompletion(**kwargs)
            except Exception as exc:  # noqa: BLE001 — every provider error means "try the next model"
                kind = classify_error(exc)
                errors.append(f"{model}: {kind}")
                log.warning("LLM %s failed (%s): %s", model, kind, str(exc)[:200])
                if kind == "rate_limited":
                    self._cooldown_until[model] = time.monotonic() + s.llm_cooldown_seconds
                elif kind in ("unavailable", "auth_error"):
                    await self.mark(model, kind, str(exc))
                continue

            text = (resp.choices[0].message.content or "").strip()
            if not text:
                errors.append(f"{model}: empty response")
                continue
            usage = getattr(resp, "usage", None)
            result = LLMResponse(
                text=text, model=model,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            if self.health.get(model, {}).get("status") != "ok":
                await self.mark(model, "ok", "last call succeeded")
            self.last_model = model
            if self.usage_repo:
                await self.usage_repo.record_llm_call({
                    "model": model, "tier": tier, "node": node, "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens, "latency_ms": result.latency_ms,
                    "fallback_depth": len(errors),
                })
            return result
        raise LLMUnavailableError("All free models are busy or unavailable: " + "; ".join(errors))
