"""Keyless remote-job boards used as the last live fallback.

Remotive asks for light use (~4 calls/day) and attribution; listings are delayed 24h.
Arbeitnow is mostly EU jobs; we keep only remote-flagged or title-relevant ones.
"""

from datetime import timedelta

from rapidfuzz import fuzz

from app.core.config import get_settings
from app.core.utils import utcnow
from app.schemas.filters import DATE_POSTED_DAYS, SearchFilters, Source, WorkType
from app.schemas.job import NormalizedJob
from app.services.job_sources.base import JobProvider, ProviderError, parse_dt
from app.services.text.jd_trimmer import strip_html


def _fresh(job: NormalizedJob, filters: SearchFilters) -> bool:
    days = DATE_POSTED_DAYS.get(filters.date_posted)
    return not days or not job.posted_at or job.posted_at >= utcnow() - timedelta(days=days)


def _relevant(title: str, query: str) -> bool:
    return fuzz.token_set_ratio(query.lower(), title.lower()) >= 45


class _RemoteBoard(JobProvider):
    def supports(self, filters: SearchFilters) -> bool:
        remote_ok = filters.work_type in (WorkType.ANY, WorkType.REMOTE)
        return remote_ok and filters.source in (Source.ALL, Source.REMOTE_BOARDS, Source.LINKEDIN, Source.NAUKRI)


class RemotiveProvider(_RemoteBoard):
    name = "remotive"
    query_words = 2
    URL = "https://remotive.com/api/remote-jobs"

    @property
    def monthly_quota(self) -> int:
        return get_settings().remotive_monthly_quota

    async def search(self, query: str, filters: SearchFilters):
        resp = await self._get(self.URL, params={"search": query, "limit": "40"})
        try:
            items = resp.json().get("jobs") or []
        except ValueError as exc:
            raise ProviderError("remotive: invalid JSON") from exc
        jobs = [self.normalize(i) for i in items]
        return [j for j in jobs if _fresh(j, filters)], None

    @staticmethod
    def normalize(item: dict) -> NormalizedJob:
        return NormalizedJob(
            source="remotive",
            external_id=str(item.get("id")),
            publisher="Remotive",
            title=item.get("title") or "Untitled",
            company=item.get("company_name") or "",
            company_logo=item.get("company_logo"),
            location=item.get("candidate_required_location") or "Remote",
            work_type="remote",
            job_type=item.get("job_type") or "",
            posted_at=parse_dt(item.get("publication_date")),
            apply_url=item.get("url") or "",
            description=strip_html(item.get("description") or ""),
            salary=item.get("salary") or None,
            attribution="Source: Remotive",
        )


class ArbeitnowProvider(_RemoteBoard):
    name = "arbeitnow"
    URL = "https://www.arbeitnow.com/api/job-board-api"

    @property
    def monthly_quota(self) -> int:
        return get_settings().arbeitnow_monthly_quota

    async def search(self, query: str, filters: SearchFilters):
        resp = await self._get(self.URL, params={"page": "1"})
        try:
            items = resp.json().get("data") or []
        except ValueError as exc:
            raise ProviderError("arbeitnow: invalid JSON") from exc
        jobs = [self.normalize(i) for i in items if _relevant(i.get("title", ""), query)]
        if filters.work_type == WorkType.REMOTE:
            jobs = [j for j in jobs if j.work_type == "remote"]
        return [j for j in jobs if _fresh(j, filters)], None

    @staticmethod
    def normalize(item: dict) -> NormalizedJob:
        return NormalizedJob(
            source="arbeitnow",
            external_id=str(item.get("slug")),
            publisher="Arbeitnow",
            title=item.get("title") or "Untitled",
            company=item.get("company_name") or "",
            location=item.get("location") or "",
            work_type="remote" if item.get("remote") else "onsite",
            job_type=", ".join(item.get("job_types") or []),
            posted_at=parse_dt(item.get("created_at")),
            apply_url=item.get("url") or "",
            description=strip_html(item.get("description") or ""),
            attribution="Source: Arbeitnow",
        )
