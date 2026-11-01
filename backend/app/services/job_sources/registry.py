"""Job-source orchestration: cache → fallback chain → store → cache.

Order: JSearch (LinkedIn/Naukri via Google for Jobs) → Adzuna → Remotive → Arbeitnow → demo.
A provider is skipped when its key is missing, its monthly quota is spent, or it
cannot serve the filters. 429/402/403 mark it exhausted and fall through.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.utils import stable_hash
from app.repositories.jobs import JobRepo
from app.repositories.usage import UsageRepo
from app.schemas.filters import SearchFilters, Source
from app.schemas.job import NormalizedJob
from app.services.job_sources.adzuna import AdzunaProvider
from app.services.job_sources.base import JobProvider, ProviderError, QuotaExceededError, search_query
from app.services.job_sources.demo import DemoProvider
from app.services.job_sources.jsearch import JSearchProvider
from app.services.job_sources.remote_boards import ArbeitnowProvider, RemotiveProvider

log = logging.getLogger(__name__)

Progress = Callable[[str], Awaitable[None] | None]

PUBLISHER_PRIORITY = (("linkedin", 0), ("naukri", 1))


def publisher_priority(publisher: str) -> int:
    """0 = LinkedIn, 1 = Naukri, 2 = everything else (the user's stated preference)."""
    p = (publisher or "").lower()
    return next((rank for key, rank in PUBLISHER_PRIORITY if key in p), 2)


@dataclass
class SearchOutcome:
    jobs: list[NormalizedJob]
    source: str
    cached: bool = False
    demo: bool = False
    attempts: list[dict] = field(default_factory=list)  # [{provider, status, detail}]


def cache_key(query: str, filters: SearchFilters) -> str:
    return stable_hash({"q": query.lower().strip(), "f": filters.cache_fields()})


def dedupe(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: dict[str, NormalizedJob] = {}
    for j in jobs:
        current = seen.get(j.dedupe_hash)
        # Prefer the copy from a higher-priority publisher.
        if current is None or publisher_priority(j.publisher) < publisher_priority(current.publisher):
            seen[j.dedupe_hash] = j
    return list(seen.values())


def apply_publisher_filter(jobs: list[NormalizedJob], source: Source) -> list[NormalizedJob]:
    """LinkedIn-only / Naukri-only: keep matching publishers when any exist."""
    if source not in (Source.LINKEDIN, Source.NAUKRI):
        return jobs
    wanted = source.value
    filtered = [j for j in jobs if wanted in j.publisher.lower()]
    return filtered or jobs


class JobSourceRegistry:
    def __init__(self, client: httpx.AsyncClient, job_repo: JobRepo, usage_repo: UsageRepo,
                 providers: list[JobProvider] | None = None):
        self.job_repo = job_repo
        self.usage_repo = usage_repo
        self.providers = providers or [
            JSearchProvider(client), AdzunaProvider(client), RemotiveProvider(client), ArbeitnowProvider(client)
        ]
        self.demo = DemoProvider(client)

    async def quota_left(self, provider: JobProvider) -> int:
        usage = await self.usage_repo.api_month(provider.name)
        if usage.get("remaining") is not None:
            return int(usage["remaining"])
        return max(0, provider.monthly_quota - int(usage.get("calls", 0)))

    async def quotas(self) -> list[dict]:
        out = []
        for p in self.providers:
            usage = await self.usage_repo.api_month(p.name)
            out.append({
                "provider": p.name, "configured": p.configured, "monthly_quota": p.monthly_quota,
                "calls_this_month": usage.get("calls", 0), "remaining": await self.quota_left(p),
            })
        return out

    async def search(self, query: str, filters: SearchFilters, *, force_refresh: bool = False,
                     progress: Progress | None = None) -> SearchOutcome:
        async def emit(msg: str):
            if progress:
                result = progress(msg)
                if hasattr(result, "__await__"):
                    await result

        ttl = get_settings().search_cache_ttl_hours
        key = cache_key(query, filters)
        if not force_refresh and (hit := await self.job_repo.cached_search(key, ttl)):
            jobs = await self.job_repo.get_many(hit["job_ids"])
            if jobs:
                await emit(f"Cache hit — reusing {len(jobs)} jobs (no API call)")
                return SearchOutcome(jobs=jobs, source=hit["source"], cached=True, demo=hit.get("demo", False))

        attempts: list[dict] = []
        for provider in self.providers:
            if not provider.configured:
                attempts.append({"provider": provider.name, "status": "skipped", "detail": "no API key"})
                continue
            if not provider.supports(filters):
                attempts.append({"provider": provider.name, "status": "skipped", "detail": "filters not supported"})
                continue
            if await self.quota_left(provider) <= 0:
                attempts.append({"provider": provider.name, "status": "skipped", "detail": "monthly quota used"})
                continue

            await emit(f"Querying {provider.name}…")
            try:
                jobs, remaining = await provider.search(search_query(query, provider.query_words), filters)
            except QuotaExceededError as exc:
                await self.usage_repo.mark_exhausted(provider.name)
                attempts.append({"provider": provider.name, "status": "quota", "detail": str(exc)})
                await emit(f"{provider.name} quota reached — falling back")
                continue
            except ProviderError as exc:
                await self.usage_repo.record_api_call(provider.name, ok=False)
                attempts.append({"provider": provider.name, "status": "error", "detail": str(exc)})
                log.warning("Job provider failed: %s", exc)
                await emit(f"{provider.name} unavailable — falling back")
                continue

            await self.usage_repo.record_api_call(provider.name, remaining=remaining)
            jobs = apply_publisher_filter(dedupe(jobs), filters.source)
            attempts.append({"provider": provider.name, "status": "ok", "detail": f"{len(jobs)} jobs"})
            if not jobs:
                continue
            await self.job_repo.upsert_many(jobs)
            await self.job_repo.save_search(key, [j.id for j in jobs], provider.name, demo=False)
            return SearchOutcome(jobs=jobs, source=provider.name, attempts=attempts)

        await emit("Live sources unavailable — serving demo data")
        jobs, _ = await self.demo.search(query, filters)
        await self.job_repo.upsert_many(jobs)
        return SearchOutcome(jobs=jobs, source="demo", demo=True, attempts=attempts)
