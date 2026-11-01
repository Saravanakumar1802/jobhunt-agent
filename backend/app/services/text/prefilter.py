"""Cheap pre-filter: rank fetched jobs in plain Python before any LLM call.

score = 0.5 * skill coverage + 0.35 * title similarity + 0.15 * experience fit
Only the top-K survive, so LLM cost is bounded no matter how many jobs the API returns.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz

from app.schemas.filters import EXPERIENCE_RANGE, Experience
from app.schemas.job import NormalizedJob
from app.services.text.jd_trimmer import extract_min_years
from app.services.text.skills import expand_implied, extract_skills

W_SKILLS, W_TITLE, W_EXPERIENCE = 0.5, 0.35, 0.15


@dataclass
class Candidate:
    job: NormalizedJob
    score: float
    job_skills: list[str]


def experience_fit(min_years: float | None, experience: Experience, years: float | None) -> float:
    """1.0 when the job's minimum fits the candidate, decaying with each missing year."""
    if min_years is None:
        return 0.7  # unknown requirement: neutral-positive
    if years is None:
        if experience == Experience.ANY:
            return 0.7
        years = EXPERIENCE_RANGE[experience][1]
    gap = min_years - years
    return 1.0 if gap <= 0 else max(0.0, 1.0 - 0.25 * gap)


def score_job(
    job: NormalizedJob, role: str, profile_skills: set[str], experience: Experience, years: float | None
) -> Candidate:
    text = f"{job.title}\n{job.description}\n" + "\n".join(job.highlights)
    job_skills = extract_skills(text)
    skills = expand_implied(profile_skills)
    coverage = len(skills & set(job_skills)) / len(job_skills) if job_skills else 0.0
    title_sim = fuzz.token_set_ratio(role.lower(), job.title.lower()) / 100
    exp = experience_fit(extract_min_years(text), experience, years)
    score = W_SKILLS * coverage + W_TITLE * title_sim + W_EXPERIENCE * exp
    return Candidate(job=job, score=round(score, 4), job_skills=job_skills)


def prefilter(
    jobs: list[NormalizedJob],
    role: str,
    profile_skills: list[str],
    *,
    experience: Experience = Experience.ANY,
    years: float | None = None,
    top_k: int = 12,
) -> list[Candidate]:
    skills = set(profile_skills)
    scored = [score_job(j, role, skills, experience, years) for j in jobs]
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]
