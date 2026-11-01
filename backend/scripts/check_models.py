"""Check every configured model against the providers' live model lists (zero tokens).

Usage (from backend/):  python -m scripts.check_models [--ping]
--ping also sends one tiny real completion per model in the chains.
"""

import asyncio
import sys

import httpx

from app.services.llm import health
from app.services.llm.client import LLMClient

ICONS = {"ok": "OK ", "unavailable": "XX ", "no_key": "-- ", "rate_limited": "~~ ", "unknown": "?? "}


async def main(ping: bool) -> None:
    llm = LLMClient()
    async with httpx.AsyncClient(timeout=20) as http:
        report = await health.check_all(llm, http)
        if ping:
            for model in llm.all_models():
                if llm.status_of(model) not in ("no_key",):
                    await health.ping(llm, model)
            report = health.report(llm, report["suggestions"])

    print("\nProviders:", ", ".join(f"{p}={'key set' if ok else 'NO KEY'}" for p, ok in report["providers"].items()))
    for tier, models in report["tiers"].items():
        print(f"\n[{tier}]  working: {report['tier_ok'][tier]}")
        for m in models:
            print(f"  {ICONS.get(m['status'], '   ')}{m['model']:<45} {m['status']:<13} {m['detail'][:70]}")
    for provider, models in report["suggestions"].items():
        if models:
            print(f"\nFree {provider} models available ({len(models)}): " + ", ".join(models[:12]))


if __name__ == "__main__":
    asyncio.run(main("--ping" in sys.argv))
