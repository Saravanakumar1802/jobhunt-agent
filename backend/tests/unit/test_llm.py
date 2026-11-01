import httpx
import litellm
import pytest
import respx
from pydantic import BaseModel

from app.core.errors import LLMUnavailableError
from app.repositories.settings import SettingsRepo
from app.repositories.usage import UsageRepo
from app.services.llm import health
from app.services.llm.client import LLMClient, classify_error
from app.services.llm.structured import complete_json, parse_json

MSG = [{"role": "user", "content": "hi"}]


def rate_limit():
    return litellm.RateLimitError("rate limit", llm_provider="groq", model="m")


def retired():
    return litellm.BadRequestError("The model `x` has been decommissioned", llm_provider="groq", model="m")


class TestClient:
    async def test_falls_back_on_rate_limit_and_cools_down(self, fake_llm, db):
        llm = LLMClient(SettingsRepo(db), UsageRepo(db))
        first = llm.chains["small"][0]
        fake_llm.script[first] = [rate_limit()]
        resp = await llm.complete("small", MSG, max_tokens=50, node="t")
        assert resp.model == llm.chains["small"][1]
        assert llm.status_of(first) == "rate_limited"
        await llm.complete("small", MSG, max_tokens=50)
        assert [c["model"] for c in fake_llm.calls].count(first) == 1  # skipped while cooling down
        logged = await UsageRepo(db).llm_today()
        assert logged and logged[-1]["fallback_depth"] == 1

    async def test_retired_model_is_marked_unavailable_and_persisted(self, fake_llm, db):
        llm = LLMClient(SettingsRepo(db), UsageRepo(db))
        first = llm.chains["mid"][0]
        fake_llm.script[first] = [retired()]
        await llm.complete("mid", MSG, max_tokens=50)
        assert llm.status_of(first) == "unavailable"
        assert (await SettingsRepo(db).get_health())[first]["status"] == "unavailable"

    async def test_all_fail_raises(self, fake_llm, db):
        llm = LLMClient()
        for m in llm.chains["small"]:
            fake_llm.script[m] = [rate_limit()]
        with pytest.raises(LLMUnavailableError):
            await llm.complete("small", MSG, max_tokens=50)

    async def test_missing_keys_skip_providers_without_calls(self, fake_llm, settings):
        settings.groq_api_key = ""
        llm = LLMClient()
        await llm.complete("small", MSG, max_tokens=50)
        assert all(not c["model"].startswith("groq/") for c in fake_llm.calls)
        assert llm.status_of(llm.chains["small"][0]) == "no_key"

    async def test_gpt_oss_gets_low_reasoning_effort_and_json_mode(self, fake_llm):
        await LLMClient().complete("small", MSG, max_tokens=50)
        call = fake_llm.calls[0]
        assert call["reasoning_effort"] == "low" and call["response_format"] == {"type": "json_object"}

    async def test_saved_chain_ignores_paid_models(self, db):
        repo = SettingsRepo(db)
        await repo.save_models(["gemini/gemini-2.5-pro", "groq/openai/gpt-oss-20b"], ["openai/gpt-4o"], "u")
        llm = LLMClient(repo)
        await llm.load()
        assert llm.chains["small"] == ["groq/openai/gpt-oss-20b"]
        assert llm.chains["mid"][0].startswith("groq/")  # paid-only list rejected → defaults kept

    def test_classify_error(self):
        assert classify_error(rate_limit()) == "rate_limited"
        assert classify_error(retired()) == "unavailable"
        assert classify_error(ValueError("boom")) == "error"


class _Out(BaseModel):
    value: int


class TestStructured:
    def test_parse_json_tolerates_fences(self):
        assert parse_json('```json\n{"value": 3}\n```') == {"value": 3}
        assert parse_json('Sure! {"value": 4} hope this helps') == {"value": 4}

    async def test_repair_retry(self, fake_llm):
        model = LLMClient().chains["small"][0]
        fake_llm.script[model] = ["not json at all", '{"value": 7}']
        out, used = await complete_json(LLMClient(), "small", "sys", "user", _Out, max_tokens=50, node="t")
        assert out.value == 7 and used == model
        assert "invalid" in fake_llm.calls[-1]["messages"][-1]["content"]


class TestHealth:
    @respx.mock
    async def test_unlisted_model_marked_unavailable_and_suggestions_free_only(self, fake_llm, http):
        respx.get(health.GROQ_MODELS).mock(return_value=httpx.Response(200, json={"data": [
            {"id": "openai/gpt-oss-20b"}, {"id": "whisper-large-v3"}, {"id": "qwen/qwen3-32b"}]}))
        respx.get(health.GEMINI_MODELS).mock(return_value=httpx.Response(200, json={"models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]}]}))
        respx.get(health.OPENROUTER_MODELS).mock(return_value=httpx.Response(200, json={"data": [
            {"id": "openai/gpt-oss-20b:free", "pricing": {"prompt": "0"}},
            {"id": "openai/gpt-4o", "pricing": {"prompt": "0.000005"}}]}))
        llm = LLMClient()
        rep = await health.check_all(llm, http)
        small = {m["model"]: m["status"] for m in rep["tiers"]["small"]}
        mid = {m["model"]: m["status"] for m in rep["tiers"]["mid"]}
        assert small["groq/openai/gpt-oss-20b"] == "ok"
        assert mid["groq/openai/gpt-oss-120b"] == "unavailable"          # not in Groq's list
        assert mid["openrouter/openai/gpt-oss-120b:free"] == "unavailable"
        assert "groq/whisper-large-v3" not in rep["suggestions"]["groq"]
        assert "gemini/gemini-2.5-pro" not in rep["suggestions"]["gemini"]
        assert rep["suggestions"]["openrouter"] == ["openrouter/openai/gpt-oss-20b:free"]
        assert rep["tier_ok"] == {"small": True, "mid": True}

    async def test_ping(self, fake_llm):
        llm = LLMClient()
        assert (await health.ping(llm, "groq/openai/gpt-oss-20b"))["status"] == "ok"
        fake_llm.script["groq/x"] = [retired()]
        assert (await health.ping(llm, "groq/x"))["status"] == "unavailable"
