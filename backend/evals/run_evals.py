"""Offline evaluation on 20 hand-labelled jobs (the demo set) for one sample profile.

Usage (from backend/):
    python -m evals.run_evals            # deterministic only (no keys needed)
    python -m evals.run_evals --llm      # full pipeline with real free LLMs (uses .env keys)

Metrics: score MAE vs labels, skill-extraction precision/recall, cache hit rate on a
repeated search, LLM calls/tokens per search, fallback rate. Prints a markdown table.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

LIVE = "--llm" in sys.argv
if not LIVE:
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        os.environ[k] = ""
for k in ("MONGODB_URI", "RAPIDAPI_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
    os.environ[k] = ""  # always evaluate on the fixed demo set, in memory

import httpx  # noqa: E402

from app.agents.deps import PipelineDeps  # noqa: E402
from app.agents.graph import run_pipeline  # noqa: E402
from app.db.memory import create_memory_db  # noqa: E402
from app.db.mongo import ensure_indexes  # noqa: E402
from app.repositories.jobs import JobRepo  # noqa: E402
from app.repositories.usage import UsageRepo  # noqa: E402
from app.schemas.filters import SearchFilters  # noqa: E402
from app.schemas.profile import ProfileIn  # noqa: E402
from app.services.job_sources.demo import DemoProvider, load_demo_jobs  # noqa: E402
from app.services.job_sources.registry import JobSourceRegistry  # noqa: E402
from app.services.llm.client import LLMClient  # noqa: E402

LABELS = json.loads((Path(__file__).parent / "labeled_jobs.json").read_text(encoding="utf-8"))


class DemoOnlyRegistry(JobSourceRegistry):
    """Use the demo provider as the only 'live' source so the cache path is exercised."""

    def __init__(self, http, job_repo, usage_repo):
        demo = DemoProvider(http)
        demo.monthly_quota = 10**6
        super().__init__(http, job_repo, usage_repo, providers=[demo])


async def run_once(deps, profile, filters):
    final = None
    async for kind, payload in run_pipeline({"profile": profile, "filters": filters}, deps):
        if kind == "result":
            final = payload
    return final


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    db = create_memory_db("evals")
    await ensure_indexes(db)
    settings_top_k = len(LABELS["labels"])
    os.environ["PREFILTER_TOP_K"] = str(settings_top_k)
    from app.core.config import get_settings

    get_settings().prefilter_top_k = settings_top_k  # score every labelled job
    usage = UsageRepo(db)
    llm = LLMClient(None, usage)
    profile = ProfileIn(**LABELS["profile"])
    filters = SearchFilters()

    async with httpx.AsyncClient() as http:
        deps = PipelineDeps(registry=DemoOnlyRegistry(http, JobRepo(db), usage), job_repo=JobRepo(db), llm=llm)
        first = await run_once(deps, profile, filters)
        calls_first = await usage.llm_today()
        second = await run_once(deps, profile, filters)
        calls_total = await usage.llm_today()

    by_ext = {r.job.external_id: r for r in first["ranked"]}
    errors, tp, fp, fn = [], 0, 0, 0
    rows = []
    for lab in LABELS["labels"]:
        r = by_ext.get(lab["external_id"])
        if not r:
            continue
        errors.append(abs(r.match.score - lab["label_score"]))
        gold = set(lab["gold_required"] + lab["gold_nice"])
        pred = set(r.analysis.required_skills + r.analysis.nice_to_have)
        tp, fp, fn = tp + len(gold & pred), fp + len(pred - gold), fn + len(gold - pred)
        rows.append((lab["title"], lab["label_score"], r.match.score, r.match.method))

    n_jobs = len(load_demo_jobs())
    tokens = sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls_first)
    fallbacks = sum(1 for c in calls_total if c.get("fallback_depth", 0) > 0)
    metrics = {
        "Mode": "LLM (hybrid)" if LIVE else "Deterministic (no LLM)",
        "Jobs evaluated": len(errors),
        "Score MAE vs hand labels (lower is better)": f"{sum(errors) / max(1, len(errors)):.1f}",
        "Within ±15 of label": f"{sum(e <= 15 for e in errors) / max(1, len(errors)):.0%}",
        "Skill extraction precision": f"{tp / max(1, tp + fp):.0%}",
        "Skill extraction recall": f"{tp / max(1, tp + fn):.0%}",
        "Job API calls (2 identical searches)": "1 (second served from cache)" if second["meta"]["cached"] else "2",
        "Analysis/match cache hits on repeat": f"{second['meta']['analysis_cache_hits']}/{n_jobs}, "
                                               f"{second['meta']['match_cache_hits']}/{n_jobs}",
        "LLM calls per fresh search": len(calls_first),
        "LLM calls on repeated search": len(calls_total) - len(calls_first),
        "Tokens per fresh search": tokens,
        "Calls that needed a fallback model": fallbacks,
    }
    print("\n| Metric | Value |\n|---|---|")
    for k, v in metrics.items():
        print(f"| {k} | {v} |")
    print("\n| Job | Label | Predicted | Method |\n|---|---|---|---|")
    for title, label, pred, method in rows:
        print(f"| {title} | {label} | {pred} | {method} |")


if __name__ == "__main__":
    asyncio.run(main())
