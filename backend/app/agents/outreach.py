"""Outreach Agent — on-demand HR message / cover letter / resume bullets.

Lazy: runs only when the user clicks "Draft". Cached per (job, profile, tone, kind).
Grounded: the prompt lists only code-computed matched skills. Never sends anything.
If every model is unavailable a deterministic template keeps the feature working.
"""

from urllib.parse import quote_plus

from app.core.errors import LLMUnavailableError
from app.core.utils import stable_hash
from app.schemas.job import JobAnalysis, MatchResult, NormalizedJob
from app.schemas.outreach import DraftKind, LLMDraft, OutreachOut, Tone
from app.schemas.profile import ProfileIn
from app.services.llm.client import LLMClient
from app.services.llm.prompts import OUTREACH_SYSTEM, outreach_user
from app.services.llm.structured import complete_json

MAX_TOKENS = {DraftKind.MESSAGE: 700, DraftKind.COVER_LETTER: 1100, DraftKind.BULLETS: 800}


def draft_key(job_id: str, profile_hash: str, tone: Tone, kind: DraftKind) -> str:
    return stable_hash([job_id, profile_hash, tone.value, kind.value])[:32]


def hr_search_url(company: str) -> str:
    """Pre-filled LinkedIn people search the user opens themselves (no scraping)."""
    keywords = f'{company} recruiter OR "talent acquisition" OR HR'
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(keywords)}"


def template_draft(job: NormalizedJob, profile: ProfileIn, match: MatchResult, tone: Tone, kind: DraftKind) -> LLMDraft:
    skills = ", ".join(match.matched_skills[:5]) or ", ".join(profile.skills[:5])
    if kind == DraftKind.BULLETS:
        lines = [f"• Built and shipped features using {s}." for s in (match.matched_skills or profile.skills)[:5]]
        return LLMDraft(subject="Resume bullets", body="\n".join(lines) or "• Add your achievements here.")
    greeting = "Hi there," if tone != Tone.FORMAL else "Dear Hiring Team,"
    body = (
        f"{greeting}\n\nI came across the {job.title} role at {job.company} and I'd love to be considered. "
        f"I work as a {profile.target_role} with hands-on experience in {skills}, which lines up well with "
        f"what the role asks for.\n\nWould you be open to a quick chat about the position?\n\n"
        f"Thanks,\n{profile.name if profile.name != 'My profile' else ''}".rstrip()
    )
    subject = f"Application for {job.title}" if kind == DraftKind.COVER_LETTER else f"Interest in the {job.title} role"
    return LLMDraft(subject=subject, body=body)


async def generate_draft(llm: LLMClient, *, job: NormalizedJob, analysis: JobAnalysis | None, match: MatchResult,
                         profile: ProfileIn, tone: Tone, kind: DraftKind) -> OutreachOut:
    user = outreach_user(
        kind=kind.value, tone=tone.value,
        job={"title": job.title, "company": job.company, "location": job.location,
             "summary": analysis.summary if analysis else ""},
        profile=profile.model_dump(), matched=match.matched_skills, missing=match.missing_skills,
    )
    try:
        draft, model = await complete_json(llm, "mid", OUTREACH_SYSTEM, user, LLMDraft,
                                           max_tokens=MAX_TOKENS[kind], node=f"outreach:{kind.value}")
        method = "llm"
    except (LLMUnavailableError, ValueError):
        draft, model, method = template_draft(job, profile, match, tone, kind), None, "template"
    return OutreachOut(job_id=job.id, tone=tone, kind=kind, subject=draft.subject, body=draft.body,
                       method=method, model=model)
