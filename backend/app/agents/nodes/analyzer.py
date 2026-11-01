"""Analyzer Agent — extract required skills per job with the small model.

Cost controls: per-job cache (shared across all profiles), trimmed JDs, batches
of N jobs per call, and grounding: any skill not literally in the posting is dropped.
Falls back to deterministic extraction if every model is unavailable.
"""

import asyncio

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.agents.deps import PipelineDeps, emit
from app.agents.state import PipelineState
from app.core.config import get_settings
from app.core.errors import LLMUnavailableError
from app.schemas.job import JobAnalysis, NormalizedJob
from app.services.llm.prompts import ANALYZER_SYSTEM, analyzer_user
from app.services.llm.structured import complete_json
from app.services.text.jd_trimmer import extract_min_years, trim_description
from app.services.text.skills import extract_skills, is_grounded, normalize_skills, split_requirements


class _Item(BaseModel):
    id: str
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    min_years: float | None = None
    seniority: str = "unknown"
    summary: str = ""


class _Batch(BaseModel):
    jobs: list[_Item]


def job_text(job: NormalizedJob) -> str:
    return f"{job.title}\n{job.description}\n" + "\n".join(job.highlights)


def deterministic_analysis(job: NormalizedJob) -> JobAnalysis:
    text = job_text(job)
    required, nice = split_requirements(text)
    return JobAnalysis(job_id=job.id, required_skills=required, nice_to_have=nice, min_years=extract_min_years(text),
                       summary=job.title, method="deterministic")


def grounded_analysis(job: NormalizedJob, item: _Item, model: str) -> JobAnalysis:
    text = job_text(job)
    required = [s for s in normalize_skills(item.required_skills) if is_grounded(s, text)]
    nice = [s for s in normalize_skills(item.nice_to_have) if is_grounded(s, text) and s not in required]
    # Union with taxonomy hits the LLM may have skipped — cheap recall boost.
    for s in extract_skills(text):
        if s not in required and s not in nice:
            nice.append(s)
    return JobAnalysis(job_id=job.id, required_skills=required, nice_to_have=nice,
                       min_years=item.min_years if item.min_years is not None else extract_min_years(text),
                       seniority=item.seniority or "unknown", summary=item.summary[:160], method="llm", model=model)


async def _analyze_batch(llm, batch: list[NormalizedJob], max_chars: int) -> list[JobAnalysis]:
    payload = [(j.id, j.title, trim_description(j.description, j.highlights, max_chars)) for j in batch]
    try:
        result, model = await complete_json(llm, "small", ANALYZER_SYSTEM, analyzer_user(payload), _Batch,
                                            max_tokens=350 * len(batch) + 400, node="analyzer")
    except (LLMUnavailableError, ValueError):
        return [deterministic_analysis(j) for j in batch]
    by_id = {it.id: it for it in result.jobs}
    return [grounded_analysis(j, by_id[j.id], model) if j.id in by_id else deterministic_analysis(j) for j in batch]


async def analyzer_node(state: PipelineState, runtime: Runtime[PipelineDeps]) -> dict:
    s = get_settings()
    jobs = [c["job"] for c in state["candidates"]]
    repo, llm = runtime.context.job_repo, runtime.context.llm
    cached = await repo.get_analyses([j.id for j in jobs])
    todo = [j for j in jobs if j.id not in cached]
    emit(runtime, "analyzer", f"Reading {len(jobs)} job descriptions ({len(cached)} cached)…",
         total=len(jobs), progress=len(cached))

    analyses = dict(cached)
    if todo:
        if llm.tier_available("small"):
            batches = [todo[i : i + s.analyzer_batch_size] for i in range(0, len(todo), s.analyzer_batch_size)]
            for coro in asyncio.as_completed([_analyze_batch(llm, b, s.jd_max_chars) for b in batches]):
                for a in await coro:
                    analyses[a.job_id] = a
                emit(runtime, "analyzer", "Extracting required skills…", total=len(jobs), progress=len(analyses))
        else:
            for j in todo:
                analyses[j.id] = deterministic_analysis(j)
        await repo.save_analyses([analyses[j.id] for j in todo])

    llm_used = sum(1 for j in todo if analyses[j.id].method == "llm")
    meta = {**state.get("meta", {})}
    if todo and llm_used == 0:
        meta["warnings"] = [*meta.get("warnings", []), "LLM unavailable for analysis — used keyword extraction."]
    emit(runtime, "analyzer", f"Analyzed {len(jobs)} jobs ({llm_used} by LLM, {len(cached)} from cache)",
         done=True, total=len(jobs), progress=len(jobs))
    return {"analyses": analyses, "meta": {**meta, "analysis_cache_hits": len(cached), "analysis_llm": llm_used}}
