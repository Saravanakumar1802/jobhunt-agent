"""Search Agent — fetch live jobs through the cached source fallback chain."""

from langgraph.runtime import Runtime

from app.agents.deps import PipelineDeps, emit
from app.agents.state import PipelineState


async def search_node(state: PipelineState, runtime: Runtime[PipelineDeps]) -> dict:
    profile, filters = state["profile"], state["filters"]
    emit(runtime, "search", f"Searching live jobs for “{profile.target_role}”…")

    outcome = await runtime.context.registry.search(
        profile.target_role, filters, force_refresh=state.get("force_refresh", False),
        progress=lambda msg: emit(runtime, "search", msg),
    )
    label = "cache" if outcome.cached else outcome.source
    emit(runtime, "search", f"Found {len(outcome.jobs)} jobs via {label}", done=True, count=len(outcome.jobs))
    return {
        "jobs": outcome.jobs,
        "meta": {"source": outcome.source, "cached": outcome.cached, "demo": outcome.demo,
                 "attempts": outcome.attempts, "fetched": len(outcome.jobs), "warnings": []},
    }
