"""App factory. Lifespan wires long-lived resources once per process:
DB connection + indexes, a pooled httpx client, the LLM client and the job-source registry,
plus a background task that re-checks model health every few hours.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import auth, jobs, profiles, search, status, tracker
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import limiter
from app.db import mongo
from app.repositories.jobs import JobRepo
from app.repositories.settings import SettingsRepo
from app.repositories.usage import UsageRepo
from app.services.job_sources.registry import JobSourceRegistry
from app.services.llm import health
from app.services.llm.client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


async def _health_loop(app: FastAPI) -> None:
    interval = get_settings().model_health_interval_hours * 3600
    while True:
        try:
            await health.check_all(app.state.llm, app.state.http)
        except Exception:  # noqa: BLE001 — never let the monitor crash the app
            log.exception("Model health check failed")
        await asyncio.sleep(interval)


async def init_services(app: FastAPI) -> None:
    s = get_settings()
    db = mongo.get_db()
    app.state.http = httpx.AsyncClient(timeout=s.http_timeout_seconds, follow_redirects=True,
                                       headers={"User-Agent": "JobHuntCopilot/1.0"})
    app.state.llm = LLMClient(SettingsRepo(db), UsageRepo(db))
    await app.state.llm.load()
    app.state.registry = JobSourceRegistry(app.state.http, JobRepo(db), UsageRepo(db))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await init_services(app)
    monitor = asyncio.create_task(_health_loop(app))
    yield
    monitor.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await monitor
    await app.state.http.aclose()
    await mongo.close()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    for r in (auth.router, profiles.router, search.router, jobs.router, tracker.router, status.router):
        app.include_router(r, prefix="/api")
    return app


app = create_app()
