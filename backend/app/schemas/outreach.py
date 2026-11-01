from enum import StrEnum

from pydantic import BaseModel, Field


class Tone(StrEnum):
    SHORT = "short"
    FRIENDLY = "friendly"
    FORMAL = "formal"


class DraftKind(StrEnum):
    MESSAGE = "message"
    COVER_LETTER = "cover_letter"
    BULLETS = "bullets"


class OutreachIn(BaseModel):
    profile_id: str
    tone: Tone = Tone.SHORT
    kind: DraftKind = DraftKind.MESSAGE


class OutreachOut(BaseModel):
    job_id: str
    tone: Tone
    kind: DraftKind
    subject: str = ""
    body: str
    method: str = "llm"
    model: str | None = None
    cached: bool = False


class LLMDraft(BaseModel):
    """Strict schema the LLM must return."""

    subject: str = Field("", max_length=140)
    body: str = Field(..., min_length=20, max_length=4000)
