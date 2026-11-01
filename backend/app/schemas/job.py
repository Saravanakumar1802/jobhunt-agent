"""One normalised job shape for every provider, plus analysis / match / ranked results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.utils import stable_hash


class NormalizedJob(BaseModel):
    id: str = ""                       # "{source}:{external_id}"
    source: str                        # provider that fetched it: jsearch | adzuna | remotive | arbeitnow | demo
    external_id: str
    publisher: str = ""                # original site, e.g. "LinkedIn", "Naukri.com"
    title: str
    company: str = ""
    company_url: str | None = None
    company_logo: str | None = None
    location: str = ""
    country: str = ""
    work_type: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    job_type: str = ""
    posted_at: datetime | None = None
    closes_at: datetime | None = None
    apply_url: str = ""
    description: str = ""
    highlights: list[str] = Field(default_factory=list)  # qualifications/responsibilities bullets
    salary: str | None = None
    attribution: str | None = None     # e.g. "Jobs by Adzuna" (required by provider terms)

    def model_post_init(self, _ctx) -> None:
        if not self.id:
            self.id = f"{self.source}:{self.external_id}"

    @property
    def dedupe_hash(self) -> str:
        """Same posting syndicated by several sources collapses to one record."""
        key = [self.title.lower().strip(), self.company.lower().strip(), self.location.lower().strip()]
        return stable_hash(key)[:24]


class JobAnalysis(BaseModel):
    """Profile-independent facts about a job — cached once per job, reused by every profile."""

    job_id: str
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    min_years: float | None = None
    seniority: str = "unknown"
    summary: str = ""
    method: Literal["llm", "deterministic"] = "deterministic"
    model: str | None = None


class MatchResult(BaseModel):
    job_id: str
    profile_hash: str
    score: int = Field(..., ge=0, le=100)
    base_score: int = Field(..., ge=0, le=100)   # deterministic part
    adjustment: int = 0                          # LLM nudge, clamped to ±15
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    missing_nice: list[str] = Field(default_factory=list)
    seniority_fit: str = "unknown"
    reasoning: str = ""
    method: Literal["llm", "deterministic"] = "deterministic"
    model: str | None = None


class RankedJob(BaseModel):
    job: NormalizedJob
    match: MatchResult
    analysis: JobAnalysis
    priority: int = 2                            # 0 LinkedIn, 1 Naukri, 2 others
    prefilter_score: float = 0.0
