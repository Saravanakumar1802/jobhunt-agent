"""Small shared helpers."""

import hashlib
import json
import uuid
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


def stable_hash(data) -> str:
    """Deterministic sha256 of any JSON-serialisable value (used for cache keys)."""
    raw = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def month_key(dt: datetime | None = None) -> str:
    return (dt or utcnow()).strftime("%Y-%m")


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Mongo returns naive UTC datetimes; normalise so comparisons never crash."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
