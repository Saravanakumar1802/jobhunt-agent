import pytest

from app.agents.nodes.ranker import rank
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.schemas.job import JobAnalysis, RankedJob
from app.services.job_sources.registry import publisher_priority
from app.services.llm.free_guard import check_free
from app.services.scoring import apply_adjustment, base_score, deterministic_match
from tests.conftest import make_job


def analysis(req, nice=(), min_years=None):
    return JobAnalysis(job_id="j", required_skills=list(req), nice_to_have=list(nice), min_years=min_years)


class TestScoring:
    def test_full_coverage_scores_100(self):
        assert base_score(["python", "react"], analysis(["python", "react"], ["docker"]), None) == 85  # 0.8 ** 0.75
        assert base_score(["python", "react", "docker"], analysis(["python", "react"], ["docker"]), None) == 100

    def test_experience_gap_penalty(self):
        a = analysis(["python"], min_years=5)
        assert base_score(["python"], a, 2) < base_score(["python"], a, 6)

    def test_sets_are_computed_in_code(self):
        m = deterministic_match("j", "h", ["python", "mern"], analysis(["python", "react", "aws"], ["docker"]), None)
        assert m.matched_skills == ["python", "react"]      # react implied by MERN
        assert m.missing_skills == ["aws"]
        assert m.missing_nice == ["docker"]

    def test_llm_adjustment_is_clamped(self):
        m = deterministic_match("j", "h", ["python"], analysis(["python"]), None)
        adjusted = apply_adjustment(m, 90, "weird", "x", "groq/test")
        assert adjusted.adjustment == 15
        assert adjusted.score == min(100, m.base_score + 15)
        assert adjusted.seniority_fit == "unknown"
        assert adjusted.matched_skills == m.matched_skills  # LLM can't change skill sets


class TestRanking:
    def test_publisher_priority(self):
        assert publisher_priority("LinkedIn") == 0
        assert publisher_priority("Naukri.com") == 1
        assert publisher_priority("Indeed") == 2

    def test_linkedin_then_naukri_then_score_and_min_score(self):
        def ranked(i, pub, score):
            job = make_job(i, publisher=pub)
            m = deterministic_match(job.id, "h", [], analysis([]), None).model_copy(update={"score": score})
            return RankedJob(job=job, match=m, analysis=analysis([]), priority=publisher_priority(pub))

        items = [ranked(1, "Indeed", 99), ranked(2, "Naukri.com", 70), ranked(3, "LinkedIn", 60),
                 ranked(4, "LinkedIn", 90), ranked(5, "Indeed", 20)]
        out = rank(items, min_score=50)
        assert [r.job.external_id for r in out] == ["ext-4", "ext-3", "ext-2", "ext-1"]


class TestFreeGuard:
    @pytest.mark.parametrize("model", [
        "groq/openai/gpt-oss-20b", "gemini/gemini-2.5-flash", "gemini/gemini-2.5-flash-lite",
        "openrouter/openai/gpt-oss-120b:free", "gemini/gemma-3-27b-it",
    ])
    def test_allows_free(self, model):
        assert check_free(model)[0]

    @pytest.mark.parametrize("model", [
        "gemini/gemini-2.5-pro", "openrouter/openai/gpt-4o", "openai/gpt-4o", "anthropic/claude",
        "groq/whisper-large-v3", "gpt-oss-20b", "gemini/gemini-2.5-flash-image",
    ])
    def test_rejects_paid_or_non_chat(self, model):
        assert not check_free(model)[0]


class TestSecurity:
    def test_password_hash_roundtrip(self):
        h = hash_password("s3cret-pass")
        assert h != "s3cret-pass"
        assert verify_password("s3cret-pass", h)
        assert not verify_password("wrong", h)

    def test_jwt_roundtrip_and_tamper(self):
        token = create_access_token("user-1")
        assert decode_access_token(token) == "user-1"
        assert decode_access_token(token + "x") is None
        assert decode_access_token("garbage") is None
