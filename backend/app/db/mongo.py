"""MongoDB connection lifecycle and index setup.

Uses PyMongo's native async driver (`AsyncMongoClient`) — Motor is deprecated.
One client per process; FastAPI's lifespan opens and closes it.
"""

import logging

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from app.core.config import get_settings
from app.db.memory import create_memory_db

log = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_db = None


async def connect() -> None:
    global _client, _db
    s = get_settings()
    if s.use_memory_db:
        log.warning("MONGODB_URI not set — using the in-memory database (data resets on restart).")
        _db = create_memory_db(s.mongodb_db)
    else:
        _client = AsyncMongoClient(s.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=8000)
        _db = _client[s.mongodb_db]
        await _db.command("ping")
        log.info("Connected to MongoDB Atlas")
    await ensure_indexes(_db)


async def close() -> None:
    global _client, _db
    if _client is not None:
        await _client.close()
    _client, _db = None, None


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialised")
    return _db


def set_db(db) -> None:
    """Test hook: inject an isolated database."""
    global _db
    _db = db


async def ensure_indexes(db) -> None:
    ttl_hours = get_settings().search_cache_ttl_hours
    await db.users.create_index("email", unique=True)
    await db.profiles.create_index("user_id")
    await db.search_cache.create_index("key", unique=True)
    await db.search_cache.create_index("created_at", expireAfterSeconds=ttl_hours * 3600)
    await db.jobs.create_index("dedupe_hash")
    await db.jobs.create_index([("fetched_at", DESCENDING)])
    await db.job_analyses.create_index("job_id", unique=True)
    await db.matches.create_index([("job_id", ASCENDING), ("profile_hash", ASCENDING)], unique=True)
    await db.outreach.create_index("key", unique=True)
    await db.tracker.create_index([("user_id", ASCENDING), ("job_id", ASCENDING)], unique=True)
    await db.api_usage.create_index([("provider", ASCENDING), ("month", ASCENDING)], unique=True)
    await db.llm_usage.create_index("ts", expireAfterSeconds=30 * 24 * 3600)
