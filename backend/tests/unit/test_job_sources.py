import httpx
import pytest
import respx

from app.repositories.jobs import JobRepo
from app.repositories.usage import UsageRepo
from app.schemas.filters import JobType, SearchFilters, Source, WorkType
from app.services.job_sources.adzuna import AdzunaProvider
from app.services.job_sources.base import QuotaExceededError
from app.services.job_sources.jsearch import JSearchProvider
from app.services.job_sources.registry import JobSourceRegistry, dedupe
from app.services.job_sources.remote_boards import ArbeitnowProvider, RemotiveProvider
from tests.conftest import make_job

JSEARCH_ITEM = {
    "job_id": "abc==", "employer_name": "Acme", "employer_website": "https://acme.test", "job_publisher": "LinkedIn",
    "job_employment_type": "FULLTIME", "job_title": "MERN Developer", "job_apply_link": "https://apply.test/1",
    "job_description": "Hybrid role. Requirements: React, Node.js", "job_is_remote": False,
    "job_posted_at_datetime_utc": "2026-10-28T10:00:00.000Z", "job_city": "Chennai", "job_state": "TN",
    "job_country": "IN", "job_offer_expiration_datetime_utc": "2026-11-30T00:00:00.000Z",
    "job_highlights": {"Qualifications": ["2+ years React"], "Responsibilities": ["Build APIs"]},
}


class TestNormalizers:
    def test_jsearch(self):
        j = JSearchProvider.normalize(JSEARCH_ITEM)
        assert j.id == "jsearch:abc=="
        assert j.publisher == "LinkedIn" and j.work_type == "hybrid"
        assert j.location == "Chennai, TN, IN" and j.closes_at.month == 11
        assert j.highlights == ["2+ years React", "Build APIs"]

    def test_adzuna(self):
        j = AdzunaProvider.normalize({"id": 9, "title": "Python Dev", "description": "Remote ok", "created": "2026-10-20T00:00:00Z",
                                      "redirect_url": "https://adz.test", "company": {"display_name": "Beta"},
                                      "location": {"display_name": "Pune"}, "salary_min": 500000, "salary_max": 900000}, "in")
        assert j.attribution == "Jobs by Adzuna" and j.company == "Beta" and j.work_type == "remote"
        assert j.salary == "500,000–900,000"

    def test_remotive_strips_html(self):
        j = RemotiveProvider.normalize({"id": 1, "title": "AI Eng", "company_name": "R", "url": "u",
                                        "publication_date": "2026-10-29T00:00:00", "description": "<p>Use <b>Python</b></p>"})
        assert j.description == "Use Python" and j.work_type == "remote"

    def test_arbeitnow(self):
        j = ArbeitnowProvider.normalize({"slug": "s1", "title": "Dev", "remote": True, "created_at": 1761800000,
                                         "description": "<p>x</p>", "url": "u", "company_name": "C"})
        assert j.external_id == "s1" and j.work_type == "remote" and j.posted_at is not None


class TestJSearchParams:
    def test_filters_are_sent_to_the_api(self, settings):
        f = SearchFilters(city="Chennai", work_type=WorkType.REMOTE, job_type=JobType.FULLTIME, source=Source.NAUKRI)
        p = JSearchProvider(None).build_params("React Developer", f)
        assert p["query"] == "React Developer in Chennai via naukri"
        assert p["work_from_home"] == "true" and p["employment_types"] == "FULLTIME"
        assert p["country"] == "in" and p["date_posted"] == "week" and p["num_pages"] == "1"

    @respx.mock
    async def test_reads_quota_header_and_maps_429(self, http, settings):
        settings.rapidapi_key = "k"
        route = respx.get("https://jsearch.p.rapidapi.com/search")
        route.return_value = httpx.Response(200, json={"data": [JSEARCH_ITEM]},
                                            headers={"x-ratelimit-requests-remaining": "41"})
        jobs, remaining = await JSearchProvider(http).search("MERN", SearchFilters())
        assert remaining == 41 and len(jobs) == 1
        assert route.calls.last.request.headers["X-RapidAPI-Key"] == "k"

        route.return_value = httpx.Response(429)
        with pytest.raises(QuotaExceededError):
            await JSearchProvider(http).search("MERN", SearchFilters())


def test_dedupe_prefers_linkedin_copy():
    a = make_job(1, title="Dev", company="X", publisher="Indeed")
    b = make_job(2, title="Dev", company="X", publisher="LinkedIn")
    assert [j.publisher for j in dedupe([a, b])] == ["LinkedIn"]


class TestRegistry:
    @pytest.fixture
    def registry(self, db, http):
        return JobSourceRegistry(http, JobRepo(db), UsageRepo(db))

    async def test_no_keys_falls_back_through_chain_to_demo(self, registry, settings):
        with respx.mock:
            respx.get("https://remotive.com/api/remote-jobs").mock(return_value=httpx.Response(503))
            respx.get("https://www.arbeitnow.com/api/job-board-api").mock(return_value=httpx.Response(200, json={"data": []}))
            out = await registry.search("Python Developer", SearchFilters())
        assert out.demo and out.source == "demo" and len(out.jobs) > 0
        statuses = {a["provider"]: a["status"] for a in out.attempts}
        assert statuses == {"jsearch": "skipped", "adzuna": "skipped", "remotive": "error", "arbeitnow": "ok"}

    async def test_quota_exhaustion_falls_back_and_cache_hit_avoids_api(self, registry, settings):
        settings.rapidapi_key = "k"
        settings.adzuna_app_id, settings.adzuna_app_key = "id", "key"
        with respx.mock:
            respx.get("https://jsearch.p.rapidapi.com/search").mock(return_value=httpx.Response(429))
            adz = respx.get("https://api.adzuna.com/v1/api/jobs/in/search/1").mock(return_value=httpx.Response(
                200, json={"results": [{"id": 1, "title": "Python Dev", "description": "Python", "company": {"display_name": "A"},
                                        "location": {"display_name": "Chennai"}, "redirect_url": "u"}]}))
            first = await registry.search("Python Developer", SearchFilters())
            second = await registry.search("python developer ", SearchFilters())
        assert first.source == "adzuna" and not first.cached
        assert second.cached and adz.call_count == 1   # cache served the repeat
        assert (await registry.usage_repo.api_month("jsearch"))["remaining"] == 0  # marked exhausted

    async def test_exhausted_quota_is_skipped_without_calling(self, registry, settings):
        settings.rapidapi_key = "k"
        settings.jsearch_monthly_quota = 1
        await registry.usage_repo.record_api_call("jsearch")
        with respx.mock(assert_all_called=False) as mock:
            js = mock.get("https://jsearch.p.rapidapi.com/search")
            mock.get("https://remotive.com/api/remote-jobs").mock(return_value=httpx.Response(200, json={"jobs": []}))
            mock.get("https://www.arbeitnow.com/api/job-board-api").mock(return_value=httpx.Response(200, json={"data": []}))
            out = await registry.search("Dev", SearchFilters())
        assert js.call_count == 0 and out.attempts[0]["detail"] == "monthly quota used"


def test_search_query_cleans_role():
    from app.services.job_sources.base import search_query

    assert search_query("MERN Stack + Python AI Engineer (Remote)") == "MERN Stack Python AI"
    assert search_query("React/Node Developer", 2) == "React Node"
    assert search_query("+") == "+"
