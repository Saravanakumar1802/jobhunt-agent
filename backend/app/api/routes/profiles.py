from fastapi import APIRouter, Response

from app.api.deps import DB, CurrentUser
from app.repositories.profiles import ProfileRepo
from app.schemas.profile import ProfileIn, ProfileOut
from app.services.text.skills import known_skills

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileOut])
async def list_profiles(user: CurrentUser, db: DB):
    return await ProfileRepo(db).list(user["_id"])


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(body: ProfileIn, user: CurrentUser, db: DB):
    return await ProfileRepo(db).create(user["_id"], body)


@router.get("/skills/suggestions", response_model=list[str])
async def skill_suggestions():
    """Canonical skill names for the skill-chip autocomplete."""
    return known_skills()


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile(profile_id: str, user: CurrentUser, db: DB):
    return await ProfileRepo(db).get(user["_id"], profile_id)


@router.put("/{profile_id}", response_model=ProfileOut)
async def update_profile(profile_id: str, body: ProfileIn, user: CurrentUser, db: DB):
    return await ProfileRepo(db).update(user["_id"], profile_id, body)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, user: CurrentUser, db: DB):
    await ProfileRepo(db).delete(user["_id"], profile_id)
    return Response(status_code=204)
