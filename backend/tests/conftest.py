"""Shared fixtures. Tests never touch real services: in-memory Mongo, respx for HTTP,
and a scripted fake for litellm.acompletion. Env vars are forced empty so a filled
`.env` can never make the unit suite spend real quota.
"""

import os

for _k in ("MONGODB_URI", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "RAPIDAPI_KEY",
           "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
    os.environ[_k] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-characters-long!!"

import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import mongo  # noqa: E402
from app.db.memory import create_memory_db  # noqa: E402
from app.schemas.job import NormalizedJob  # noqa: E402


@pytest.fixture
def settings():
    s = get_settings()
    original = s.model_dump()
    yield s
    for k, v in original.items():
        setattr(s, k, v)


@pytest.fixture
async def db():
    memdb = create_memory_db("test")
    await mongo.ensure_indexes(memdb)
    mongo.set_db(memdb)
    yield memdb
    mongo.set_db(None)


def fake_response(text: str, prompt_tokens: int = 50, completion_tokens: int = 20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class FakeLiteLLM:
    """Scriptable replacement for litellm.acompletion.

    `script` maps a model id to a list of outcomes (str reply or Exception). When a model's
    script is exhausted or missing, `default(kwargs)` builds a schema-correct reply.
    """

    def __init__(self):
        self.calls: list[dict] = []
        self.script: dict[str, list] = {}

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        queue = self.script.get(kwargs["model"])
        if queue:
            outcome = queue.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return fake_response(outcome)
        return fake_response(self.default(kwargs))

    @staticmethod
    def default(kwargs) -> str:
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][-1]["content"]
        ids = [line.split("id:", 1)[1].strip() for line in user.splitlines() if line.startswith("### id:")]
        if "extract hiring requirements" in system:
            return json.dumps({"jobs": [{"id": i, "required_skills": ["python", "react", "kubernetes-imaginary"],
                                          "nice_to_have": ["docker"], "min_years": 2, "seniority": "mid",
                                          "summary": "Builds things"} for i in ids]})
        if "review how well a candidate fits" in system:
            return json.dumps({"jobs": [{"id": i, "fit_adjustment": 5, "seniority_fit": "good",
                                          "reasoning": "Solid overlap."} for i in ids]})
        return json.dumps({"subject": "Hello", "body": "Hi there, I am excited about this role and my skills fit."})


@pytest.fixture
def fake_llm(monkeypatch, settings):
    fake = FakeLiteLLM()
    monkeypatch.setattr("app.services.llm.client.litellm.acompletion", fake)
    monkeypatch.setattr("litellm.acompletion", fake)
    settings.groq_api_key = "test-groq"
    settings.gemini_api_key = "test-gemini"
    settings.openrouter_api_key = "test-or"
    return fake


@pytest.fixture
async def http():
    async with httpx.AsyncClient() as client:
        yield client


def make_job(i: int = 1, *, title="Python Developer", publisher="LinkedIn", desc=None, **kw) -> NormalizedJob:
    return NormalizedJob(
        source=kw.pop("source", "jsearch"), external_id=f"ext-{i}", publisher=publisher, title=title,
        company=kw.pop("company", f"Company {i}"), location=kw.pop("location", "Chennai, India"),
        description=desc or "Requirements:\n- 2+ years with Python, React and MongoDB\nBenefits:\nFree lunch",
        **kw,
    )
