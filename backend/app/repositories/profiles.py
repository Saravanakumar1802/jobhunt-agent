from pymongo import DESCENDING

from app.core.errors import NotFoundError
from app.core.utils import new_id, utcnow
from app.schemas.profile import ProfileIn, ProfileOut


def _out(doc: dict) -> ProfileOut:
    return ProfileOut(id=doc["_id"], **{k: v for k, v in doc.items() if k not in ("_id", "user_id")})


class ProfileRepo:
    def __init__(self, db):
        self.col = db["profiles"]

    async def list(self, user_id: str) -> list[ProfileOut]:
        docs = await self.col.find({"user_id": user_id}).sort("updated_at", DESCENDING).to_list(50)
        return [_out(d) for d in docs]

    async def get(self, user_id: str, profile_id: str) -> ProfileOut:
        doc = await self.col.find_one({"_id": profile_id, "user_id": user_id})
        if not doc:
            raise NotFoundError("Profile not found")
        return _out(doc)

    async def create(self, user_id: str, data: ProfileIn) -> ProfileOut:
        now = utcnow()
        doc = {"_id": new_id(), "user_id": user_id, **data.model_dump(), "created_at": now, "updated_at": now}
        await self.col.insert_one(doc)
        return _out(doc)

    async def update(self, user_id: str, profile_id: str, data: ProfileIn) -> ProfileOut:
        res = await self.col.update_one(
            {"_id": profile_id, "user_id": user_id}, {"$set": {**data.model_dump(), "updated_at": utcnow()}}
        )
        if res.matched_count == 0:
            raise NotFoundError("Profile not found")
        return await self.get(user_id, profile_id)

    async def delete(self, user_id: str, profile_id: str) -> None:
        res = await self.col.delete_one({"_id": profile_id, "user_id": user_id})
        if res.deleted_count == 0:
            raise NotFoundError("Profile not found")
