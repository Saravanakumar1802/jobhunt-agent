"""JSearch (OpenWeb Ninja via RapidAPI) — Google for Jobs data incl. LinkedIn and Naukri.

Primary source. Free Basic plan is hard-limited (no card). Filters are mapped to
the API's own parameters so one request returns already-narrowed results.
"""

from app.core.config import get_settings
from app.schemas.filters import DatePosted, Experience, JobType, SearchFilters, Source, WorkType
from app.schemas.job import NormalizedJob
from app.services.job_sources.base import JobProvider, ProviderError, infer_work_type, parse_dt, work_type_ok

URL = "https://jsearch.p.rapidapi.com/search"
HOST = "jsearch.p.rapidapi.com"

DATE_MAP = {DatePosted.ANY: "all", DatePosted.DAY: "today", DatePosted.THREE_DAYS: "3days",
            DatePosted.WEEK: "week", DatePosted.MONTH: "month"}
TYPE_MAP = {JobType.FULLTIME: "FULLTIME", JobType.PARTTIME: "PARTTIME",
            JobType.CONTRACT: "CONTRACTOR", JobType.INTERNSHIP: "INTERN"}
EXP_MAP = {Experience.FRESHER: "no_experience", Experience.JUNIOR: "under_3_years_experience",
           Experience.MID: "more_than_3_years_experience", Experience.SENIOR: "more_than_3_years_experience"}
# Steering the Google-for-Jobs query toward one publisher.
PUBLISHER_HINT = {Source.LINKEDIN: "via linkedin", Source.NAUKRI: "via naukri"}


class JSearchProvider(JobProvider):
    name = "jsearch"

    @property
    def configured(self) -> bool:
        return bool(get_settings().rapidapi_key)

    @property
    def monthly_quota(self) -> int:
        return get_settings().jsearch_monthly_quota

    def supports(self, filters: SearchFilters) -> bool:
        return filters.source in (Source.ALL, Source.LINKEDIN, Source.NAUKRI)

    def build_params(self, query: str, filters: SearchFilters) -> dict:
        q = query
        if filters.city and not filters.anywhere:
            q += f" in {filters.city}"
        if hint := PUBLISHER_HINT.get(filters.source):
            q += f" {hint}"
        params = {"query": q, "page": "1", "num_pages": "1", "date_posted": DATE_MAP[filters.date_posted]}
        if not filters.anywhere:
            params["country"] = filters.country
        if filters.work_type == WorkType.REMOTE:
            params["work_from_home"] = "true"
        if t := TYPE_MAP.get(filters.job_type):
            params["employment_types"] = t
        if e := EXP_MAP.get(filters.experience):
            params["job_requirements"] = e
        return params

    async def search(self, query: str, filters: SearchFilters):
        resp = await self._get(
            URL,
            params=self.build_params(query, filters),
            headers={"X-RapidAPI-Key": get_settings().rapidapi_key, "X-RapidAPI-Host": HOST},
        )
        try:
            data = resp.json().get("data") or []
        except ValueError as exc:
            raise ProviderError("jsearch: invalid JSON") from exc
        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        jobs = [self.normalize(item) for item in data]
        jobs = [j for j in jobs if work_type_ok(j.work_type, filters.work_type)]
        return jobs, int(remaining) if remaining and remaining.isdigit() else None

    @staticmethod
    def normalize(item: dict) -> NormalizedJob:
        hl = item.get("job_highlights") or {}
        highlights = [*hl.get("Qualifications", []), *hl.get("Responsibilities", [])]
        location = ", ".join(p for p in (item.get("job_city"), item.get("job_state"), item.get("job_country")) if p)
        desc = item.get("job_description") or ""
        salary = None
        if item.get("job_min_salary") and item.get("job_max_salary"):
            salary = f"{item['job_min_salary']:,.0f}–{item['job_max_salary']:,.0f} {item.get('job_salary_currency') or ''}".strip()
        return NormalizedJob(
            source="jsearch",
            external_id=str(item.get("job_id")),
            publisher=item.get("job_publisher") or "",
            title=item.get("job_title") or "Untitled",
            company=item.get("employer_name") or "",
            company_url=item.get("employer_website"),
            company_logo=item.get("employer_logo"),
            location=location or ("Remote" if item.get("job_is_remote") else ""),
            country=(item.get("job_country") or "").lower(),
            work_type=infer_work_type(f"{item.get('job_title', '')} {desc[:1500]}", item.get("job_is_remote")),
            job_type=item.get("job_employment_type") or "",
            posted_at=parse_dt(item.get("job_posted_at_datetime_utc")),
            closes_at=parse_dt(item.get("job_offer_expiration_datetime_utc")),
            apply_url=item.get("job_apply_link") or item.get("job_google_link") or "",
            description=desc,
            highlights=highlights,
            salary=salary,
        )
