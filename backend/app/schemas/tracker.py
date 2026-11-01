from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class TrackStatus(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"


class TrackIn(BaseModel):
    job_id: str
    status: TrackStatus = TrackStatus.SAVED
    notes: str = Field("", max_length=2000)
    hr_profile_url: HttpUrl | None = None


class TrackPatch(BaseModel):
    status: TrackStatus | None = None
    notes: str | None = Field(None, max_length=2000)
    hr_profile_url: HttpUrl | None = None


class TrackOut(BaseModel):
    job_id: str
    status: TrackStatus
    notes: str = ""
    hr_profile_url: str | None = None
    score: int | None = None
    job: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
