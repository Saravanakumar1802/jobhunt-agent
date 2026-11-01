"""Services injected into graph nodes through LangGraph's typed runtime context.

`graph.astream(state, context=PipelineDeps(...))` hands every node a
`Runtime[PipelineDeps]`, so nodes stay pure functions of (state, runtime) and
are trivial to unit-test with fakes.
"""

from dataclasses import dataclass

from langgraph.runtime import Runtime

from app.repositories.jobs import JobRepo
from app.services.job_sources.registry import JobSourceRegistry
from app.services.llm.client import LLMClient


@dataclass
class PipelineDeps:
    registry: JobSourceRegistry
    job_repo: JobRepo
    llm: LLMClient


def emit(runtime: Runtime, stage: str, message: str, **data) -> None:
    """Push a progress event to the UI (no-op unless streaming with mode 'custom')."""
    runtime.stream_writer({"stage": stage, "message": message, **data})
