"""Search filters. Sent to the job APIs themselves so they return fewer, more relevant jobs."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class WorkType(StrEnum):
    ANY = "any"
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class JobType(StrEnum):
    ANY = "any"
    FULLTIME = "fulltime"
    PARTTIME = "parttime"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class Experience(StrEnum):
    ANY = "any"
    FRESHER = "fresher"
    JUNIOR = "1-3"
    MID = "3-5"
    SENIOR = "5+"


class DatePosted(StrEnum):
    ANY = "any"
    DAY = "24h"
    THREE_DAYS = "3d"
    WEEK = "7d"
    MONTH = "30d"


class Source(StrEnum):
    ALL = "all"          # JSearch first, ranked LinkedIn → Naukri → others
    LINKEDIN = "linkedin"
    NAUKRI = "naukri"
    ADZUNA = "adzuna"
    REMOTE_BOARDS = "remote_boards"  # Remotive + Arbeitnow


DATE_POSTED_DAYS = {DatePosted.DAY: 1, DatePosted.THREE_DAYS: 3, DatePosted.WEEK: 7, DatePosted.MONTH: 30}

# (min_years, max_years) used for experience-fit scoring
EXPERIENCE_RANGE = {
    Experience.FRESHER: (0, 1),
    Experience.JUNIOR: (1, 3),
    Experience.MID: (3, 5),
    Experience.SENIOR: (5, 30),
}


class SearchFilters(BaseModel):
    country: str = Field("in", min_length=2, max_length=2, description="ISO-3166 alpha-2")
    city: str = Field("", max_length=80)
    anywhere: bool = False
    work_type: WorkType = WorkType.ANY
    job_type: JobType = JobType.ANY
    experience: Experience = Experience.ANY
    date_posted: DatePosted = DatePosted.WEEK
    source: Source = Source.ALL
    min_score: int = Field(0, ge=0, le=100)

    @field_validator("country")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("city")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    def cache_fields(self) -> dict:
        """Fields that change what the job API returns (min_score is applied locally)."""
        return self.model_dump(mode="json", exclude={"min_score"})
