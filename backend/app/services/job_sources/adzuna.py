"""Adzuna — own index across ~19 countries incl. India. Free key, 2,500 calls/month.

Terms require crediting "Jobs by Adzuna" next to listings (see `attribution`).
"""

from app.core.config import get_settings
from app.schemas.filters import DATE_POSTED_DAYS, JobType, SearchFilters, Source, WorkType
from app.schemas.job import NormalizedJob
from app.services.job_sources.base import JobProvider, ProviderError, infer_work_type, parse_dt, work_type_ok

URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"
COUNTRIES = {"gb", "us", "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "in", "it", "mx", "nl", "nz", "pl", "sg", "za"}
TYPE_FLAG = {JobType.FULLTIME: "full_time", JobType.PARTTIME: "part_time", JobType.CONTRACT: "contract"}


class AdzunaProvider(JobProvider):
    name = "adzuna"

    @property
    def configured(self) -> bool:
        s = get_settings()
        return bool(s.adzuna_app_id and s.adzuna_app_key)

    @property
    def monthly_quota(self) -> int:
        return get_settings().adzuna_monthly_quota

    def supports(self, filters: SearchFilters) -> bool:
        country_ok = filters.anywhere or filters.country in COUNTRIES
        return filters.source in (Source.ALL, Source.ADZUNA, Source.LINKEDIN, Source.NAUKRI) and country_ok

    def build_params(self, query: str, filters: SearchFilters) -> dict:
        s = get_settings()
        what = query + (" remote" if filters.work_type == WorkType.REMOTE else "")
        params = {"app_id": s.adzuna_app_id, "app_key": s.adzuna_app_key, "results_per_page": "20",
                  "what": what, "content-type": "application/json"}
        if filters.city and not filters.anywhere:
            params["where"] = filters.city
        if days := DATE_POSTED_DAYS.get(filters.date_posted):
            params["max_days_old"] = str(days)
        if flag := TYPE_FLAG.get(filters.job_type):
            params[flag] = "1"
        return params

    async def search(self, query: str, filters: SearchFilters):
        country = "in" if filters.anywhere or filters.country not in COUNTRIES else filters.country
        resp = await self._get(URL.format(country=country), params=self.build_params(query, filters))
        try:
            results = resp.json().get("results") or []
        except ValueError as exc:
            raise ProviderError("adzuna: invalid JSON") from exc
        jobs = [self.normalize(r, country) for r in results]
        return [j for j in jobs if work_type_ok(j.work_type, filters.work_type)], None

    @staticmethod
    def normalize(item: dict, country: str) -> NormalizedJob:
        desc = item.get("description") or ""
        salary = None
        if item.get("salary_min") and item.get("salary_max"):
            salary = f"{item['salary_min']:,.0f}–{item['salary_max']:,.0f}"
        return NormalizedJob(
            source="adzuna",
            external_id=str(item.get("id")),
            publisher="Adzuna",
            title=item.get("title") or "Untitled",
            company=(item.get("company") or {}).get("display_name", ""),
            location=(item.get("location") or {}).get("display_name", ""),
            country=country,
            work_type=infer_work_type(f"{item.get('title', '')} {desc}"),
            job_type=" ".join(filter(None, (item.get("contract_time"), item.get("contract_type")))),
            posted_at=parse_dt(item.get("created")),
            apply_url=item.get("redirect_url") or "",
            description=desc,
            salary=salary,
            attribution="Jobs by Adzuna",
        )
