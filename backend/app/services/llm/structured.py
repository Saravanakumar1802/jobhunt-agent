"""Structured output: ask for JSON, validate with Pydantic, one repair retry."""

import json
import re

from pydantic import BaseModel, ValidationError

from app.services.llm.client import LLMClient

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json(text: str) -> dict:
    """Tolerate code fences and leading/trailing chatter around one JSON object."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(cleaned[start : end + 1])


async def complete_json[T: BaseModel](llm: LLMClient, tier: str, system: str, user: str, schema: type[T], *,
                        max_tokens: int, node: str) -> tuple[T, str]:
    """Return (validated object, model id). Raises LLMUnavailableError / ValueError."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = await llm.complete(tier, messages, max_tokens=max_tokens, node=node)
    try:
        return schema.model_validate(parse_json(resp.text)), resp.model
    except (ValueError, ValidationError) as exc:
        repair = messages + [
            {"role": "assistant", "content": resp.text[:4000]},
            {"role": "user", "content": f"That was invalid ({str(exc)[:300]}). Reply with ONLY the corrected JSON object."},
        ]
        resp = await llm.complete(tier, repair, max_tokens=max_tokens, node=f"{node}:repair")
        return schema.model_validate(parse_json(resp.text)), resp.model
