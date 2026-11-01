"""Quota counters for job APIs and token/model logs for LLM calls."""

from datetime import timedelta

from pymongo import DESCENDING

from app.core.utils import month_key, utcnow


class UsageRepo:
    def __init__(self, db):
        self.api = db["api_usage"]
        self.llm = db["llm_usage"]
        self.events = db["search_events"]

    # --- job API quota --------------------------------------------------------
    async def api_month(self, provider: str) -> dict:
        doc = await self.api.find_one({"provider": provider, "month": month_key()})
        return doc or {"provider": provider, "month": month_key(), "calls": 0, "remaining": None}

    async def record_api_call(self, provider: str, *, remaining: int | None = None, ok: bool = True) -> None:
        update: dict = {"$inc": {"calls": 1, "errors": 0 if ok else 1}, "$set": {"last_call_at": utcnow()}}
        if remaining is not None:
            update["$set"]["remaining"] = remaining
        await self.api.update_one({"provider": provider, "month": month_key()}, update, upsert=True)

    async def mark_exhausted(self, provider: str) -> None:
        await self.api.update_one(
            {"provider": provider, "month": month_key()}, {"$set": {"remaining": 0, "last_call_at": utcnow()}}, upsert=True
        )

    # --- LLM usage --------------------------------------------------------------
    async def record_llm_call(self, entry: dict) -> None:
        await self.llm.insert_one({**entry, "ts": utcnow()})

    async def llm_today(self) -> list[dict]:
        since = utcnow() - timedelta(hours=24)
        return await self.llm.find({"ts": {"$gte": since}}, {"_id": 0}).sort("ts", DESCENDING).to_list(2000)

    # --- search events (for the status panel + evals) -----------------------------
    async def record_search(self, entry: dict) -> None:
        await self.events.insert_one({**entry, "ts": utcnow()})

    async def recent_searches(self, limit: int = 50) -> list[dict]:
        return await self.events.find({}, {"_id": 0}).sort("ts", DESCENDING).to_list(limit)
