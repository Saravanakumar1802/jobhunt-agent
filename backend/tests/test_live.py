"""Live smoke tests against real APIs. Opt-in: `pytest -m live` (uses keys from backend/.env).

Each test spends at most one request of the corresponding free quota and skips if
the key is missing.
"""

import httpx
import pytest
from dotenv import dotenv_values

from app.schemas.filters import SearchFilters
from app.services.job_sources.adzuna import AdzunaProvider
from app.services.job_sources.jsearch import JSearchProvider
from app.services.llm.client import LLMClient

pytestmark = pytest.mark.live
ENV = {k.lower(): v for k, v in dotenv_values(".env").items() if v}


@pytest.fixture(autouse=True)
def real_keys(settings):
    for k, v in ENV.items():
        if hasattr(settings, k):
            setattr(settings, k, v)


def need(*keys):
    missing = [k for k in keys if k not in ENV]
    if missing:
        pytest.skip(f"missing {', '.join(missing)} in .env")


@pytest.mark.parametrize("tier", ["small", "mid"])
async def test_llm_tier_answers(tier):
    llm = LLMClient()
    if not llm.configured_providers():
        pytest.skip("no LLM keys in .env")
    resp = await llm.complete(tier, [{"role": "user", "content": 'Return {"ok": true} as JSON'}], max_tokens=200)
    assert "ok" in resp.text.lower()
    print(f"\n{tier} answered by {resp.model} in {resp.latency_ms} ms")


async def test_jsearch():
    need("rapidapi_key")
    async with httpx.AsyncClient(timeout=30) as http:
        jobs, remaining = await JSearchProvider(http).search("React Developer", SearchFilters())
    print(f"\nJSearch: {len(jobs)} jobs, publishers={sorted({j.publisher for j in jobs})}, remaining={remaining}")
    assert isinstance(jobs, list)


async def test_adzuna():
    need("adzuna_app_id", "adzuna_app_key")
    async with httpx.AsyncClient(timeout=30) as http:
        jobs, _ = await AdzunaProvider(http).search("Python Developer", SearchFilters())
    print(f"\nAdzuna: {len(jobs)} jobs")
    assert isinstance(jobs, list)
