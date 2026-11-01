"""In-memory async stand-in for PyMongo's AsyncMongoClient (backed by mongomock).

Used when MONGODB_URI is empty so the app runs before Atlas is configured, and
by the test suite. Only the subset of the async API this project uses is
mirrored. Data is lost on restart and TTL indexes do not expire documents —
repositories therefore also check freshness themselves.
"""

from typing import Any

import mongomock


class MemoryCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs) -> "MemoryCursor":
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, n: int) -> "MemoryCursor":
        self._cursor = self._cursor.limit(n)
        return self

    def skip(self, n: int) -> "MemoryCursor":
        self._cursor = self._cursor.skip(n)
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = list(self._cursor)
        return docs if length is None else docs[:length]

    def __aiter__(self):
        self._iter = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class MemoryCollection:
    def __init__(self, collection):
        self._c = collection

    def find(self, *args, **kwargs) -> MemoryCursor:
        return MemoryCursor(self._c.find(*args, **kwargs))

    async def bulk_write(self, ops, ordered: bool = True):
        # mongomock's bulk_write is incompatible with current PyMongo operation objects.
        for op in ops:
            self._c.update_one(op._filter, op._doc, upsert=bool(op._upsert))

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._c, name)
        if not callable(attr):
            return attr

        async def _async(*args, **kwargs):
            return attr(*args, **kwargs)

        return _async


class MemoryDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> MemoryCollection:
        return MemoryCollection(self._db[name])

    __getattr__ = __getitem__

    async def command(self, *_args, **_kwargs) -> dict:
        return {"ok": 1}


def create_memory_db(name: str = "job_copilot") -> MemoryDatabase:
    return MemoryDatabase(mongomock.MongoClient(tz_aware=True)[name])
