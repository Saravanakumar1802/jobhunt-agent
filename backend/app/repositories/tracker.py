from pymongo import DESCENDING

from app.core.errors import NotFoundError
from app.core.utils import utcnow
from app.schemas.tracker import TrackIn, TrackPatch


class TrackerRepo:
    def __init__(self, db):
        self.col = db["tracker"]

    async def list(self, user_id: str) -> list[dict]:
        return await self.col.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", DESCENDING).to_list(500)

    async def get(self, user_id: str, job_id: str) -> dict | None:
        return await self.col.find_one({"user_id": user_id, "job_id": job_id}, {"_id": 0})

    async def upsert(self, user_id: str, data: TrackIn, *, job: dict, score: int | None) -> dict:
        now = utcnow()
        fields = data.model_dump(mode="json")
        await self.col.update_one(
            {"user_id": user_id, "job_id": data.job_id},
            {"$set": {**fields, "job": job, "score": score, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return await self.get(user_id, data.job_id)

    async def patch(self, user_id: str, job_id: str, data: TrackPatch) -> dict:
        fields = data.model_dump(mode="json", exclude_unset=True)
        res = await self.col.update_one(
            {"user_id": user_id, "job_id": job_id}, {"$set": {**fields, "updated_at": utcnow()}}
        )
        if res.matched_count == 0:
            raise NotFoundError("Tracked job not found")
        return await self.get(user_id, job_id)

    async def delete(self, user_id: str, job_id: str) -> None:
        res = await self.col.delete_one({"user_id": user_id, "job_id": job_id})
        if res.deleted_count == 0:
            raise NotFoundError("Tracked job not found")
