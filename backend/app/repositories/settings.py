"""Runtime-editable settings (LLM model chains, model health) stored in Mongo."""

from app.core.utils import utcnow


class SettingsRepo:
    def __init__(self, db):
        self.col = db["app_settings"]
        self.outreach = db["outreach"]

    async def get_models(self) -> dict | None:
        return await self.col.find_one({"_id": "models"})

    async def save_models(self, small: list[str], mid: list[str], user_id: str) -> None:
        await self.col.update_one(
            {"_id": "models"},
            {"$set": {"small": small, "mid": mid, "updated_by": user_id, "updated_at": utcnow()}},
            upsert=True,
        )

    async def get_health(self) -> dict:
        doc = await self.col.find_one({"_id": "model_health"})
        return (doc or {}).get("models", {})

    async def save_health(self, models: dict) -> None:
        await self.col.update_one(
            {"_id": "model_health"}, {"$set": {"models": models, "updated_at": utcnow()}}, upsert=True
        )

    # --- outreach draft cache ----------------------------------------------------
    async def get_draft(self, key: str) -> dict | None:
        return await self.outreach.find_one({"key": key}, {"_id": 0})

    async def save_draft(self, key: str, draft: dict) -> None:
        await self.outreach.update_one({"key": key}, {"$set": {**draft, "key": key, "created_at": utcnow()}}, upsert=True)
