"""Provider contract every job source implements.

Adding a source = one new subclass + one line in the registry chain.
"""

import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime

import httpx

from app.schemas.filters import SearchFilters


class QuotaExceededError(Exception):
    """Provider answered 429 / monthly quota is spent — move to the next source."""


class ProviderError(Exception):
    """Provider failed (network, 5xx, bad payload) — move to the next source."""


class JobProvider(ABC):
    name: str = "base"
    monthly_quota: int = 0
    query_words: int = 5  # keyword boards (Remotive) do better with shorter queries

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @property
    def configured(self) -> bool:
        """False when the provider's API key is missing."""
        return True

    def supports(self, filters: SearchFilters) -> bool:
        return True

    @abstractmethod
    async def search(self, query: str, filters: SearchFilters) -> tuple[list, int | None]:
        """Return (normalised jobs, remaining quota if the API reports it)."""

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        try:
            resp = await self.client.get(url, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: {exc.__class__.__name__}") from exc
        if resp.status_code < 400:
            return resp
        detail = f"{self.name}: HTTP {resp.status_code}{api_message(resp)}"
        # 403 is usually "not subscribed" / bad key: a setup problem, so don't zero the month's quota for it.
        if resp.status_code in (402, 429):
            raise QuotaExceededError(detail)
        raise ProviderError(detail)


def api_message(resp: httpx.Response) -> str:
    """The provider's own error text, e.g. ' (You are not subscribed to this API.)'."""
    try:
        msg = resp.json().get("message")
    except (ValueError, AttributeError):
        msg = None
    return f" ({str(msg)[:120]})" if msg else ""


HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
REMOTE_RE = re.compile(r"\b(remote|work from home|wfh)\b", re.IGNORECASE)


def infer_work_type(text: str, is_remote: bool | None = None) -> str:
    if HYBRID_RE.search(text or ""):
        return "hybrid"
    if is_remote or REMOTE_RE.search(text or ""):
        return "remote"
    return "onsite" if is_remote is False else "unknown"


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


_QUERY_NOISE = re.compile(r"\([^)]*\)|[+/&|,;:]")


def search_query(role: str, max_words: int = 4) -> str:
    """Turn a free-text role into a job-board query.

    "MERN Stack + Python AI Engineer (Remote)" → "MERN Stack Python AI". Long, symbol-heavy
    queries match almost nothing on keyword job boards.
    """
    words = _QUERY_NOISE.sub(" ", role).split()
    return " ".join(words[:max_words]) or role.strip()


def work_type_ok(job_work_type: str, wanted: str) -> bool:
    """Post-filter for providers that cannot filter work type server-side."""
    return wanted == "any" or job_work_type in (wanted, "unknown")
