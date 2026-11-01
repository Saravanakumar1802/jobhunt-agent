"""Shared LangGraph state. Each node reads what it needs and returns only the keys it changes."""

from typing import Any, TypedDict

from app.schemas.filters import SearchFilters
from app.schemas.job import JobAnalysis, MatchResult, NormalizedJob, RankedJob
from app.schemas.profile import ProfileIn


class PipelineState(TypedDict, total=False):
    # inputs
    profile: ProfileIn
    filters: SearchFilters
    force_refresh: bool
    # produced by nodes
    jobs: list[NormalizedJob]               # search
    candidates: list[dict[str, Any]]        # prefilter: [{"job", "score"}]
    analyses: dict[str, JobAnalysis]        # analyzer
    matches: dict[str, MatchResult]         # matcher
    ranked: list[RankedJob]                 # ranker
    meta: dict[str, Any]                    # source, cached, demo, counts, models, warnings
