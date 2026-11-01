"""POST /search — runs the agent graph and streams progress as Server-Sent Events.

Events:  progress {stage, message, ...}  →  result {jobs, meta}  |  error {code, message}
POST (not GET) because the body carries profile + filters; the frontend reads the
stream with fetch + ReadableStream since EventSource only supports GET.
"""

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agents.deps import PipelineDeps
from app.agents.graph import run_pipeline
from app.api.deps import DB, LLM, CurrentUser, Registry
from app.core.rate_limit import limiter
from app.repositories.jobs import JobRepo
from app.repositories.profiles import ProfileRepo
from app.repositories.usage import UsageRepo
from app.schemas.profile import ProfileIn
from app.schemas.search import SearchIn

router = APIRouter(tags=["search"])
log = logging.getLogger(__name__)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/search")
@limiter.limit("15/hour")
async def search(request: Request, body: SearchIn, user: CurrentUser, db: DB, llm: LLM, registry: Registry):
    if body.profile_id:
        saved = await ProfileRepo(db).get(user["_id"], body.profile_id)
        profile = ProfileIn(**saved.model_dump(exclude={"id", "created_at", "updated_at"}))
    else:
        profile = body.profile

    deps = PipelineDeps(registry=registry, job_repo=JobRepo(db), llm=llm)
    state = {"profile": profile, "filters": body.filters, "force_refresh": body.force_refresh}

    async def stream():
        started = time.perf_counter()
        yield sse("progress", {"stage": "start", "message": "Agents are waking up…"})
        try:
            async for kind, payload in run_pipeline(state, deps):
                if await request.is_disconnected():
                    return
                if kind == "progress":
                    yield sse("progress", payload)
                    continue
                ranked = payload.get("ranked", [])
                meta = {**payload.get("meta", {}), "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "profile_hash": profile.profile_hash(), "last_model": llm.last_model}
                await UsageRepo(db).record_search({
                    "user_id": user["_id"], "source": meta.get("source"), "cached": meta.get("cached"),
                    "demo": meta.get("demo"), "fetched": meta.get("fetched", 0), "ranked": len(ranked),
                    "elapsed_ms": meta["elapsed_ms"], "analysis_cache_hits": meta.get("analysis_cache_hits", 0),
                    "match_cache_hits": meta.get("match_cache_hits", 0),
                })
                yield sse("result", {"jobs": [r.model_dump(mode="json") for r in ranked], "meta": meta})
        except Exception as exc:  # noqa: BLE001 — surface to the UI instead of a broken stream
            log.exception("Search pipeline failed")
            yield sse("error", {"code": "pipeline_error", "message": str(exc)[:300]})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
