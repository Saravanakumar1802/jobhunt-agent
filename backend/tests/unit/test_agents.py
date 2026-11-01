import httpx
import respx

from app.agents.deps import PipelineDeps
from app.agents.graph import run_pipeline
from app.agents.nodes.analyzer import _Item, grounded_analysis
from app.agents.outreach import generate_draft, hr_search_url, template_draft
from app.repositories.jobs import JobRepo
from app.repositories.usage import UsageRepo
from app.schemas.filters import SearchFilters
from app.schemas.outreach import DraftKind, Tone
from app.schemas.profile import ProfileIn
from app.services.job_sources.registry import JobSourceRegistry
from app.services.llm.client import LLMClient
from app.services.scoring import deterministic_match
from tests.conftest import make_job

PROFILE = ProfileIn(name="Sam", target_role="MERN Stack Developer", skills=["react", "node.js", "mongodb", "python"],
                    years_experience=2)


def _mock_remote_boards(mock):
    mock.get("https://remotive.com/api/remote-jobs").mock(return_value=httpx.Response(200, json={"jobs": []}))
    mock.get("https://www.arbeitnow.com/api/job-board-api").mock(return_value=httpx.Response(200, json={"data": []}))


async def _run(db, http, llm, filters=None):
    deps = PipelineDeps(registry=JobSourceRegistry(http, JobRepo(db), UsageRepo(db)), job_repo=JobRepo(db), llm=llm)
    events, final = [], None
    async for kind, payload in run_pipeline({"profile": PROFILE, "filters": filters or SearchFilters()}, deps):
        if kind == "progress":
            events.append(payload)
        else:
            final = payload
    return events, final


def test_grounding_drops_invented_skills():
    job = make_job(1, desc="Requirements: Python and React. Docker is a plus.")
    a = grounded_analysis(job, _Item(id=job.id, required_skills=["Python", "ReactJS", "Kubernetes"],
                                     nice_to_have=["docker", "aws"]), "groq/x")
    assert a.required_skills == ["python", "react"]
    assert a.nice_to_have == ["docker"]


async def test_pipeline_without_llm_uses_deterministic_scoring(db, http):
    with respx.mock as mock:
        _mock_remote_boards(mock)
        events, final = await _run(db, http, LLMClient())
    stages = [e["stage"] for e in events]
    assert stages[0] == "search" and {"prefilter", "analyzer", "matcher", "ranker"} <= set(stages)
    ranked = final["ranked"]
    assert final["meta"]["demo"] and 0 < len(ranked) <= 12
    assert all(r.match.method == "deterministic" for r in ranked)
    # LinkedIn group first, then Naukri
    prios = [r.priority for r in ranked]
    assert prios == sorted(prios)
    assert any("keyword extraction" in w for w in final["meta"]["warnings"])


async def test_pipeline_with_llm_batches_and_caches(db, http, fake_llm):
    llm = LLMClient(None, UsageRepo(db))
    with respx.mock as mock:
        _mock_remote_boards(mock)
        _, first = await _run(db, http, llm)
        calls_after_first = len(fake_llm.calls)
        _, second = await _run(db, http, llm)
    n = len(first["ranked"])
    assert all(r.match.method == "llm" for r in first["ranked"])
    assert all("kubernetes-imaginary" not in r.analysis.required_skills for r in first["ranked"])  # grounded
    assert calls_after_first == 2 * ((n + 3) // 4)   # batches of 4 for analyzer + matcher
    assert len(fake_llm.calls) == calls_after_first  # second run: zero LLM calls (caches)
    assert second["meta"]["analysis_cache_hits"] == n and second["meta"]["match_cache_hits"] == n


async def test_min_score_filter(db, http):
    with respx.mock as mock:
        _mock_remote_boards(mock)
        _, final = await _run(db, http, LLMClient(), SearchFilters(min_score=100))
    assert all(r.match.score >= 100 for r in final["ranked"])
    assert final["meta"]["hidden_below_min"] >= 0


class TestOutreach:
    def test_hr_link(self):
        url = hr_search_url("Acme Labs")
        assert url.startswith("https://www.linkedin.com/search/results/people/?keywords=Acme+Labs+recruiter")

    def test_template_only_uses_matched_skills(self):
        job = make_job(1)
        from app.schemas.job import JobAnalysis
        m = deterministic_match(job.id, "h", PROFILE.skills, JobAnalysis(job_id=job.id, required_skills=["python", "aws"]), 2)
        d = template_draft(job, PROFILE, m, Tone.FRIENDLY, DraftKind.MESSAGE)
        assert "python" in d.body and "aws" not in d.body

    async def test_llm_draft_and_template_fallback(self, fake_llm):
        job = make_job(1)
        from app.schemas.job import JobAnalysis
        m = deterministic_match(job.id, "h", PROFILE.skills, JobAnalysis(job_id=job.id, required_skills=["python"]), 2)
        out = await generate_draft(LLMClient(), job=job, analysis=None, match=m, profile=PROFILE,
                                   tone=Tone.SHORT, kind=DraftKind.MESSAGE)
        assert out.method == "llm" and out.subject == "Hello"
        assert "Matched skills: python" in fake_llm.calls[-1]["messages"][-1]["content"]

        llm = LLMClient()
        for model in llm.chains["mid"]:
            fake_llm.script[model] = [ValueError("down")] * 3
        out = await generate_draft(llm, job=job, analysis=None, match=m, profile=PROFILE,
                                   tone=Tone.FORMAL, kind=DraftKind.COVER_LETTER)
        assert out.method == "template" and out.body.startswith("Dear Hiring Team")
