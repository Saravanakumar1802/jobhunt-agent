"""Status panel (quotas, usage, health) and the Models page (view / test / switch models)."""

from collections import Counter

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import DB, LLM, AdminUser, CurrentUser, Registry
from app.core.config import DEFAULT_MID_MODELS, DEFAULT_SMALL_MODELS, get_settings
from app.repositories.usage import UsageRepo
from app.services.llm import health
from app.services.llm.free_guard import check_free

router = APIRouter(tags=["status"])


@router.get("/health")
async def liveness():
    return {"ok": True}


@router.get("/status")
async def status(user: CurrentUser, db: DB, llm: LLM, registry: Registry):
    usage = UsageRepo(db)
    calls = await usage.llm_today()
    searches = await usage.recent_searches(50)
    by_model = Counter(c["model"] for c in calls)
    total = len(searches) or 1
    return {
        "database": "memory" if get_settings().use_memory_db else "atlas",
        "job_sources": await registry.quotas(),
        "llm": {
            "calls_24h": len(calls),
            "tokens_24h": sum(c.get("prompt_tokens", 0) + c.get("completion_tokens", 0) for c in calls),
            "by_model": dict(by_model),
            "fallback_calls_24h": sum(1 for c in calls if c.get("fallback_depth", 0) > 0),
            "last_model": llm.last_model,
            "tier_ok": {t: llm.tier_available(t) for t in llm.chains},
        },
        "searches": {
            "recent": searches[:10],
            "cache_hit_rate": round(sum(1 for s in searches if s.get("cached")) / total, 3),
            "demo_rate": round(sum(1 for s in searches if s.get("demo")) / total, 3),
        },
    }


@router.get("/models")
async def models(user: CurrentUser, llm: LLM):
    return health.report(llm)


@router.post("/models/check")
async def models_check(request: Request, user: CurrentUser, llm: LLM):
    """Refresh health from providers' model lists (zero tokens) and return suggestions."""
    return await health.check_all(llm, request.app.state.http)


class PingIn(BaseModel):
    model: str


@router.post("/models/test")
async def models_test(body: PingIn, user: AdminUser, llm: LLM):
    ok, reason = check_free(body.model)
    if not ok:
        return {"model": body.model, "status": "rejected", "detail": reason}
    return await health.ping(llm, body.model)


class ChainsIn(BaseModel):
    small: list[str] = Field(..., min_length=1, max_length=6)
    mid: list[str] = Field(..., min_length=1, max_length=6)

    @field_validator("small", "mid")
    @classmethod
    def _free_only(cls, v: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(m.strip() for m in v if m.strip()))
        for m in cleaned:
            ok, reason = check_free(m)
            if not ok:
                raise ValueError(f"{m}: {reason}")
        return cleaned


@router.put("/models")
async def save_models(body: ChainsIn, user: AdminUser, llm: LLM):
    await llm.set_chains(body.small, body.mid, user["_id"])
    return health.report(llm)


@router.post("/models/reset")
async def reset_models(user: AdminUser, llm: LLM):
    await llm.set_chains(list(DEFAULT_SMALL_MODELS), list(DEFAULT_MID_MODELS), user["_id"])
    return health.report(llm)
