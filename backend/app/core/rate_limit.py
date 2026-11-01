"""Per-visitor rate limiting (slowapi). Keyed by user id when authenticated, else IP."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import decode_access_token


def _key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        user_id = decode_access_token(auth[7:])
        if user_id:
            return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key, enabled=get_settings().rate_limit_enabled)
