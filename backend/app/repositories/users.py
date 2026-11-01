from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError
from app.core.utils import new_id, utcnow


class UserRepo:
    def __init__(self, db):
        self.col = db["users"]

    async def create(self, *, name: str, email: str, password_hash: str) -> dict:
        # The first account becomes admin (can change model settings).
        is_admin = await self.col.count_documents({}) == 0
        doc = {
            "_id": new_id(), "name": name, "email": email.lower(),
            "password_hash": password_hash, "is_admin": is_admin, "created_at": utcnow(),
        }
        try:
            await self.col.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ConflictError("An account with this email already exists") from exc
        return doc

    async def by_email(self, email: str) -> dict | None:
        return await self.col.find_one({"email": email.lower()})

    async def by_id(self, user_id: str) -> dict | None:
        return await self.col.find_one({"_id": user_id})
