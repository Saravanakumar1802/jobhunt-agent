from fastapi import APIRouter, Request

from app.agents.nodes.analyzer import deterministic_analysis
from app.agents.outreach import draft_key, generate_draft, hr_search_url
from app.api.deps import DB, LLM, CurrentUser
from app.core.errors import NotFoundError
from app.core.rate_limit import limiter
from app.repositories.jobs import JobRepo
from app.repositories.profiles import ProfileRepo
from app.repositories.settings import SettingsRepo
from app.schemas.outreach import OutreachIn, OutreachOut
from app.schemas.profile import ProfileIn
from app.services.scoring import deterministic_match

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _job_or_404(repo: JobRepo, job_id: str):
    job = await repo.get(job_id)
    if not job:
        raise NotFoundError("Job not found")
    return job


@router.get("/{job_id:path}/hr-search-link")
async def hr_link(job_id: str, user: CurrentUser, db: DB):
    job = await _job_or_404(JobRepo(db), job_id)
    return {"company": job.company, "url": hr_search_url(job.company)}


@router.post("/{job_id:path}/outreach", response_model=OutreachOut)
@limiter.limit("40/hour")
async def outreach(request: Request, job_id: str, body: OutreachIn, user: CurrentUser, db: DB, llm: LLM):
    repo, settings = JobRepo(db), SettingsRepo(db)
    job = await _job_or_404(repo, job_id)
    saved = await ProfileRepo(db).get(user["_id"], body.profile_id)
    profile = ProfileIn(**saved.model_dump(exclude={"id", "created_at", "updated_at"}))
    phash = profile.profile_hash()

    key = draft_key(job.id, phash, body.tone, body.kind)
    if cached := await settings.get_draft(key):
        fields = {k: v for k, v in cached.items() if k in OutreachOut.model_fields and k != "cached"}
        return OutreachOut(**fields, cached=True)

    analysis = await repo.get_analysis(job.id)
    match = await repo.get_match(job.id, phash)
    if match is None:
        analysis = analysis or deterministic_analysis(job)
        match = deterministic_match(job.id, phash, profile.skills, analysis, profile.years_experience)

    draft = await generate_draft(llm, job=job, analysis=analysis, match=match, profile=profile,
                                 tone=body.tone, kind=body.kind)
    if draft.method == "llm":  # don't cache template fallbacks — retry the LLM next time
        await settings.save_draft(key, draft.model_dump(mode="json"))
    return draft


@router.get("/{job_id:path}")
async def get_job(job_id: str, user: CurrentUser, db: DB):
    job = await _job_or_404(JobRepo(db), job_id)
    return job.model_dump(mode="json")
