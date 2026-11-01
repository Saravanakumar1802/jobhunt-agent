"""Pre-filter — zero-token Python ranking that caps how many jobs reach the LLM."""

from langgraph.runtime import Runtime

from app.agents.deps import PipelineDeps, emit
from app.agents.state import PipelineState
from app.core.config import get_settings
from app.services.text.prefilter import prefilter


async def prefilter_node(state: PipelineState, runtime: Runtime[PipelineDeps]) -> dict:
    profile, filters, jobs = state["profile"], state["filters"], state["jobs"]
    top_k = get_settings().prefilter_top_k
    emit(runtime, "prefilter", f"Scoring {len(jobs)} jobs locally (no LLM)…")
    kept = prefilter(jobs, profile.target_role, profile.skills, experience=filters.experience,
                     years=profile.years_experience, top_k=top_k)
    emit(runtime, "prefilter", f"Kept top {len(kept)} of {len(jobs)} candidates", done=True, count=len(kept))
    return {"candidates": [{"job": c.job, "score": c.score} for c in kept]}
