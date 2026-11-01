from fastapi import APIRouter, Request

from app.api.deps import DB, CurrentUser
from app.core.errors import AuthError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.users import UserRepo
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(doc: dict) -> UserOut:
    return UserOut(id=doc["_id"], name=doc["name"], email=doc["email"], is_admin=doc.get("is_admin", False))


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("10/hour")
async def register(request: Request, body: RegisterIn, db: DB):
    user = await UserRepo(db).create(name=body.name, email=body.email, password_hash=hash_password(body.password))
    return TokenOut(access_token=create_access_token(user["_id"]), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
@limiter.limit("20/minute")
async def login(request: Request, body: LoginIn, db: DB):
    user = await UserRepo(db).by_email(body.email)
    # Same error for unknown email and wrong password — don't leak which accounts exist.
    if not user or not verify_password(body.password, user["password_hash"]):
        raise AuthError("Incorrect email or password")
    return TokenOut(access_token=create_access_token(user["_id"]), user=_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return _user_out(user)
