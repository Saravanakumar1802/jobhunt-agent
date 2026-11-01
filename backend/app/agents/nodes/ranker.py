"""Ranker — apply the min-score filter and order LinkedIn → Naukri → others, best match first."""

from langgraph.runtime import Runtime

from app.agents.deps import PipelineDeps, emit
from app.agents.state import PipelineState
from app.schemas.job import RankedJob
from app.services.job_sources.registry import publisher_priority


def rank(items: list[RankedJob], min_score: int) -> list[RankedJob]:
    kept = [r for r in items if r.match.score >= min_score]
    return sorted(kept, key=lambda r: (r.priority, -r.match.score, -r.prefilter_score))


async def ranker_node(state: PipelineState, runtime: Runtime[PipelineDeps]) -> dict:
    analyses, matches = state["analyses"], state["matches"]
    items = [
        RankedJob(job=c["job"], match=matches[c["job"].id], analysis=analyses[c["job"].id],
                  priority=publisher_priority(c["job"].publisher), prefilter_score=c["score"])
        for c in state["candidates"]
    ]
    ranked = rank(items, state["filters"].min_score)
    hidden = len(items) - len(ranked)
    emit(runtime, "ranker", f"Ranked {len(ranked)} jobs" + (f" ({hidden} below your min score)" if hidden else ""),
         done=True, count=len(ranked))
    return {"ranked": ranked, "meta": {**state.get("meta", {}), "hidden_below_min": hidden}}
