from fastapi import APIRouter, Query, Response

from app.api.deps import DB, CurrentUser
from app.core.errors import NotFoundError
from app.repositories.jobs import JobRepo
from app.repositories.tracker import TrackerRepo
from app.schemas.tracker import TrackIn, TrackOut, TrackPatch

router = APIRouter(prefix="/tracker", tags=["tracker"])

# Snapshot of the fields the tracker card needs, so the list renders without joins.
JOB_SNAPSHOT = ("id", "title", "company", "location", "work_type", "publisher", "apply_url", "company_url", "posted_at")


@router.get("", response_model=list[TrackOut])
async def list_tracked(user: CurrentUser, db: DB):
    return await TrackerRepo(db).list(user["_id"])


@router.post("", response_model=TrackOut, status_code=201)
async def track(body: TrackIn, user: CurrentUser, db: DB, profile_hash: str | None = Query(None)):
    jobs = JobRepo(db)
    job = await jobs.get(body.job_id)
    if not job:
        raise NotFoundError("Job not found")
    match = await jobs.get_match(job.id, profile_hash) if profile_hash else None
    snapshot = {k: v for k, v in job.model_dump(mode="json").items() if k in JOB_SNAPSHOT}
    return await TrackerRepo(db).upsert(user["_id"], body, job=snapshot, score=match.score if match else None)


@router.patch("/{job_id:path}", response_model=TrackOut)
async def update_tracked(job_id: str, body: TrackPatch, user: CurrentUser, db: DB):
    return await TrackerRepo(db).patch(user["_id"], job_id, body)


@router.delete("/{job_id:path}", status_code=204)
async def untrack(job_id: str, user: CurrentUser, db: DB):
    await TrackerRepo(db).delete(user["_id"], job_id)
    return Response(status_code=204)
