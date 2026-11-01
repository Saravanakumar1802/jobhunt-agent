"""Sample dataset served when every live source is unavailable — the demo never breaks."""

import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

from app.core.utils import utcnow
from app.schemas.filters import SearchFilters, WorkType
from app.schemas.job import NormalizedJob
from app.services.job_sources.base import JobProvider

DEMO_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_jobs.json"


@lru_cache
def _raw() -> list[dict]:
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def load_demo_jobs() -> list[NormalizedJob]:
    now = utcnow()
    jobs = []
    for item in _raw():
        data = {k: v for k, v in item.items() if k not in ("posted_days_ago", "closes_in_days")}
        data["posted_at"] = now - timedelta(days=item["posted_days_ago"])
        data["closes_at"] = now + timedelta(days=item["closes_in_days"]) if item.get("closes_in_days") else None
        data["attribution"] = "Demo data"
        jobs.append(NormalizedJob(**data))
    return jobs


class DemoProvider(JobProvider):
    name = "demo"

    async def search(self, query: str, filters: SearchFilters):
        jobs = load_demo_jobs()
        if filters.work_type != WorkType.ANY:
            jobs = [j for j in jobs if j.work_type == filters.work_type]
        # Light relevance ordering; the real ranking happens in the agent pipeline.
        jobs.sort(key=lambda j: fuzz.token_set_ratio(query.lower(), j.title.lower()), reverse=True)
        return jobs, None
