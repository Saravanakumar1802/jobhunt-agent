"""Matcher Agent — hybrid score (deterministic base + bounded LLM nudge) per job.

Cached per (job, profile_hash): re-running the same profile costs zero tokens.
"""

import asyncio

from langgraph.runtime import Runtime
from pydantic import BaseModel

from app.agents.deps import PipelineDeps, emit
from app.agents.state import PipelineState
from app.core.config import get_settings
from app.core.errors import LLMUnavailableError
from app.schemas.job import MatchResult
from app.services.llm.prompts import MATCHER_SYSTEM, matcher_user
from app.services.llm.structured import complete_json
from app.services.scoring import apply_adjustment, deterministic_match


class _Item(BaseModel):
    id: str
    fit_adjustment: int = 0
    seniority_fit: str = "unknown"
    reasoning: str = ""


class _Batch(BaseModel):
    jobs: list[_Item]


async def _judge_batch(llm, profile: dict, items: list[dict], base: dict[str, MatchResult]) -> list[MatchResult]:
    try:
        result, model = await complete_json(llm, "mid", MATCHER_SYSTEM, matcher_user(profile, items), _Batch,
                                            max_tokens=180 * len(items) + 400, node="matcher")
    except (LLMUnavailableError, ValueError):
        return [base[it["id"]] for it in items]
    by_id = {r.id: r for r in result.jobs}
    out = []
    for it in items:
        m = base[it["id"]]
        if r := by_id.get(it["id"]):
            m = apply_adjustment(m, r.fit_adjustment, r.seniority_fit, r.reasoning, model)
        out.append(m)
    return out


async def matcher_node(state: PipelineState, runtime: Runtime[PipelineDeps]) -> dict:
    s = get_settings()
    profile, analyses = state["profile"], state["analyses"]
    jobs = [c["job"] for c in state["candidates"]]
    phash = profile.profile_hash()
    repo, llm = runtime.context.job_repo, runtime.context.llm

    cached = await repo.get_matches([j.id for j in jobs], phash)
    todo = [j for j in jobs if j.id not in cached]
    emit(runtime, "matcher", f"Scoring your fit for {len(jobs)} jobs ({len(cached)} cached)…",
         total=len(jobs), progress=len(cached))

    matches = dict(cached)
    base = {j.id: deterministic_match(j.id, phash, profile.skills, analyses[j.id], profile.years_experience) for j in todo}
    if todo and llm.tier_available("mid"):
        items = [{"id": j.id, "title": j.title, "seniority": analyses[j.id].seniority,
                  "min_years": analyses[j.id].min_years, "base_score": base[j.id].base_score,
                  "matched": base[j.id].matched_skills, "missing": base[j.id].missing_skills,
                  "summary": analyses[j.id].summary} for j in todo]
        pdict = profile.model_dump()
        batches = [items[i : i + s.matcher_batch_size] for i in range(0, len(items), s.matcher_batch_size)]
        for coro in asyncio.as_completed([_judge_batch(llm, pdict, b, base) for b in batches]):
            for m in await coro:
                matches[m.job_id] = m
            emit(runtime, "matcher", "Judging seniority & domain fit…", total=len(jobs), progress=len(matches))
    else:
        matches.update(base)
    await repo.save_matches([matches[j.id] for j in todo])

    emit(runtime, "matcher", f"Scored {len(jobs)} jobs", done=True, total=len(jobs), progress=len(jobs))
    return {"matches": matches, "meta": {**state.get("meta", {}), "match_cache_hits": len(cached)}}
