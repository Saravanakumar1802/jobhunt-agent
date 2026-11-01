"""Hybrid match scoring — the anti-hallucination core.

Matched / missing skills are pure set operations on normalised skills, so the
LLM can never claim a skill the candidate doesn't have. The LLM only returns a
bounded nudge (±15) for things code can't judge (domain, seniority).
"""

from app.schemas.job import JobAnalysis, MatchResult
from app.services.text.skills import expand_implied

REQUIRED_WEIGHT, NICE_WEIGHT = 0.8, 0.2
MAX_ADJUST = 15
# Concave curve fitted on evals/labeled_jobs.json: people rate 70% coverage as a strong match, not a 70.
CALIBRATION = 0.75


def clamp(v: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(v))))


def skill_sets(profile_skills: list[str], analysis: JobAnalysis) -> tuple[list[str], list[str], list[str]]:
    have = expand_implied(profile_skills)
    required, nice = analysis.required_skills, analysis.nice_to_have
    matched = [s for s in dict.fromkeys(required + nice) if s in have]
    missing = [s for s in required if s not in have]
    missing_nice = [s for s in nice if s not in have]
    return matched, missing, missing_nice


def base_score(profile_skills: list[str], analysis: JobAnalysis, years: float | None) -> int:
    have = expand_implied(profile_skills)
    req, nice = analysis.required_skills, analysis.nice_to_have
    req_cov = sum(s in have for s in req) / len(req) if req else 0.5
    nice_cov = sum(s in have for s in nice) / len(nice) if nice else 0.5
    score = 100 * (REQUIRED_WEIGHT * req_cov + NICE_WEIGHT * nice_cov) ** CALIBRATION
    if analysis.min_years is not None and years is not None and analysis.min_years > years:
        score -= min(25, 8 * (analysis.min_years - years))  # each missing year costs 8 points
    return clamp(score)


def deterministic_match(job_id: str, profile_hash: str, profile_skills: list[str], analysis: JobAnalysis,
                        years: float | None) -> MatchResult:
    matched, missing, missing_nice = skill_sets(profile_skills, analysis)
    base = base_score(profile_skills, analysis, years)
    return MatchResult(job_id=job_id, profile_hash=profile_hash, score=base, base_score=base, adjustment=0,
                       matched_skills=matched, missing_skills=missing, missing_nice=missing_nice,
                       reasoning=_auto_reason(matched, missing), method="deterministic")


def apply_adjustment(match: MatchResult, adjustment: int, seniority_fit: str, reasoning: str, model: str) -> MatchResult:
    adj = max(-MAX_ADJUST, min(MAX_ADJUST, int(adjustment)))
    return match.model_copy(update={
        "adjustment": adj, "score": clamp(match.base_score + adj),
        "seniority_fit": seniority_fit if seniority_fit in ("under", "good", "over") else "unknown",
        "reasoning": (reasoning or match.reasoning)[:280], "method": "llm", "model": model,
    })


def _auto_reason(matched: list[str], missing: list[str]) -> str:
    if not matched:
        return "Few of the listed skills overlap with your profile."
    text = f"Matches {len(matched)} skills ({', '.join(matched[:4])})"
    return text + (f"; missing {', '.join(missing[:3])}." if missing else "; no required skills missing.")
