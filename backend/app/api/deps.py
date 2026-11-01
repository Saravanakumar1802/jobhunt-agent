"""FastAPI dependencies: auth, repositories and long-lived services from app.state."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.db.mongo import get_db
from app.repositories.jobs import JobRepo
from app.repositories.profiles import ProfileRepo
from app.repositories.settings import SettingsRepo
from app.repositories.tracker import TrackerRepo
from app.repositories.usage import UsageRepo
from app.repositories.users import UserRepo
from app.services.job_sources.registry import JobSourceRegistry
from app.services.llm.client import LLMClient

_bearer = HTTPBearer(auto_error=False)


def db_dep():
    return get_db()


DB = Annotated[object, Depends(db_dep)]


async def current_user(db: DB, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not creds:
        raise AuthError("Missing bearer token")
    user_id = decode_access_token(creds.credentials)
    user = await UserRepo(db).by_id(user_id) if user_id else None
    if not user:
        raise AuthError("Invalid or expired token")
    return user


async def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user.get("is_admin"):
        raise ForbiddenError("Only the admin (first registered account) can change model settings")
    return user


CurrentUser = Annotated[dict, Depends(current_user)]
AdminUser = Annotated[dict, Depends(admin_user)]


def llm_dep(request: Request) -> LLMClient:
    return request.app.state.llm


def registry_dep(request: Request) -> JobSourceRegistry:
    return request.app.state.registry


LLM = Annotated[LLMClient, Depends(llm_dep)]
Registry = Annotated[JobSourceRegistry, Depends(registry_dep)]


def repos(db) -> dict:
    return {"jobs": JobRepo(db), "profiles": ProfileRepo(db), "tracker": TrackerRepo(db),
            "usage": UsageRepo(db), "settings": SettingsRepo(db), "users": UserRepo(db)}
