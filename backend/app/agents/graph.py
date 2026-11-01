"""LangGraph wiring: search → prefilter → analyzer → matcher → ranker.

    START ─► search ──(no jobs)──► END
               │
               ▼
           prefilter ─► analyzer ─► matcher ─► ranker ─► END

Compiled once per process. Outreach is NOT part of this graph — it runs lazily
when the user clicks "Draft message" (see agents/outreach.py).
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.deps import PipelineDeps
from app.agents.nodes.analyzer import analyzer_node
from app.agents.nodes.matcher import matcher_node
from app.agents.nodes.prefilter import prefilter_node
from app.agents.nodes.ranker import ranker_node
from app.agents.nodes.search import search_node
from app.agents.state import PipelineState


def _after_search(state: PipelineState) -> str:
    return "prefilter" if state.get("jobs") else END


@lru_cache
def build_graph():
    g = StateGraph(PipelineState, context_schema=PipelineDeps)
    g.add_node("search", search_node)
    g.add_node("prefilter", prefilter_node)
    g.add_node("analyzer", analyzer_node)
    g.add_node("matcher", matcher_node)
    g.add_node("ranker", ranker_node)
    g.add_edge(START, "search")
    g.add_conditional_edges("search", _after_search, ["prefilter", END])
    g.add_edge("prefilter", "analyzer")
    g.add_edge("analyzer", "matcher")
    g.add_edge("matcher", "ranker")
    g.add_edge("ranker", END)
    return g.compile()


async def run_pipeline(state: PipelineState, deps: PipelineDeps):
    """Yield ("progress", event) for each node update, then ("result", final_state)."""
    final: dict = dict(state)
    async for mode, chunk in build_graph().astream(state, context=deps, stream_mode=["custom", "updates"]):
        if mode == "custom":
            yield "progress", chunk
        else:
            for update in chunk.values():
                if update:
                    final.update(update)
    yield "result", final
