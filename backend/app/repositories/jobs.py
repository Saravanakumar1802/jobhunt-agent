"""Job store + search cache + analysis/match caches.

Storing every fetched job means re-ranking for a different profile, or reopening
a job, never costs another job-API call.
"""

from datetime import timedelta

from pymongo import UpdateOne

from app.core.utils import ensure_aware, utcnow
from app.schemas.job import JobAnalysis, MatchResult, NormalizedJob


class JobRepo:
    def __init__(self, db):
        self.jobs = db["jobs"]
        self.cache = db["search_cache"]
        self.analyses = db["job_analyses"]
        self.matches = db["matches"]

    # --- jobs ---------------------------------------------------------------
    async def upsert_many(self, jobs: list[NormalizedJob]) -> None:
        if not jobs:
            return
        now = utcnow()
        ops = [
            UpdateOne(
                {"_id": j.id},
                {"$set": {**j.model_dump(exclude={"id"}), "dedupe_hash": j.dedupe_hash, "fetched_at": now}},
                upsert=True,
            )
            for j in jobs
        ]
        await self.jobs.bulk_write(ops, ordered=False)

    async def get(self, job_id: str) -> NormalizedJob | None:
        doc = await self.jobs.find_one({"_id": job_id})
        return _job(doc) if doc else None

    async def get_many(self, job_ids: list[str]) -> list[NormalizedJob]:
        docs = await self.jobs.find({"_id": {"$in": job_ids}}).to_list(None)
        by_id = {d["_id"]: _job(d) for d in docs}
        return [by_id[i] for i in job_ids if i in by_id]

    # --- search cache -------------------------------------------------------
    async def cached_search(self, key: str, ttl_hours: int) -> dict | None:
        doc = await self.cache.find_one({"key": key})
        # TTL index removes old docs eventually; check freshness explicitly too.
        if doc and ensure_aware(doc["created_at"]) > utcnow() - timedelta(hours=ttl_hours):
            return doc
        return None

    async def save_search(self, key: str, job_ids: list[str], source: str, demo: bool) -> None:
        await self.cache.update_one(
            {"key": key},
            {"$set": {"job_ids": job_ids, "source": source, "demo": demo, "created_at": utcnow()}},
            upsert=True,
        )

    # --- LLM result caches ----------------------------------------------------
    async def get_analyses(self, job_ids: list[str]) -> dict[str, JobAnalysis]:
        docs = await self.analyses.find({"job_id": {"$in": job_ids}}).to_list(None)
        return {d["job_id"]: JobAnalysis(**_strip(d)) for d in docs}

    async def save_analyses(self, items: list[JobAnalysis]) -> None:
        if items:
            await self.analyses.bulk_write(
                [UpdateOne({"job_id": a.job_id}, {"$set": a.model_dump()}, upsert=True) for a in items],
                ordered=False,
            )

    async def get_matches(self, job_ids: list[str], profile_hash: str) -> dict[str, MatchResult]:
        docs = await self.matches.find({"job_id": {"$in": job_ids}, "profile_hash": profile_hash}).to_list(None)
        return {d["job_id"]: MatchResult(**_strip(d)) for d in docs}

    async def get_match(self, job_id: str, profile_hash: str) -> MatchResult | None:
        doc = await self.matches.find_one({"job_id": job_id, "profile_hash": profile_hash})
        return MatchResult(**_strip(doc)) if doc else None

    async def get_analysis(self, job_id: str) -> JobAnalysis | None:
        doc = await self.analyses.find_one({"job_id": job_id})
        return JobAnalysis(**_strip(doc)) if doc else None

    async def save_matches(self, items: list[MatchResult]) -> None:
        if items:
            await self.matches.bulk_write(
                [
                    UpdateOne({"job_id": m.job_id, "profile_hash": m.profile_hash}, {"$set": m.model_dump()}, upsert=True)
                    for m in items
                ],
                ordered=False,
            )


def _strip(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


def _job(doc: dict) -> NormalizedJob:
    data = {k: v for k, v in doc.items() if k not in ("_id", "dedupe_hash", "fetched_at")}
    return NormalizedJob(id=doc["_id"], **data)
