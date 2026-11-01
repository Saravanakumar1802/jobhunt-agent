from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.utils import stable_hash
from app.services.text.skills import normalize_skills


class ProfileIn(BaseModel):
    name: str = Field("My profile", min_length=1, max_length=60)
    target_role: str = Field(..., min_length=2, max_length=100)
    description: str = Field("", max_length=2000)
    skills: list[str] = Field(..., min_length=1, max_length=60)
    years_experience: float | None = Field(None, ge=0, le=50)

    @field_validator("skills")
    @classmethod
    def _normalize(cls, v: list[str]) -> list[str]:
        skills = normalize_skills(v)
        if not skills:
            raise ValueError("at least one skill is required")
        return skills

    def profile_hash(self) -> str:
        """Identity for match caching: any change to role/skills/experience invalidates scores."""
        return stable_hash(
            {"role": self.target_role.lower().strip(), "skills": sorted(self.skills), "years": self.years_experience}
        )[:24]


class ProfileOut(ProfileIn):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
