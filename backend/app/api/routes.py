from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.app.core.config import get_settings
from backend.app.models.schemas import AnalyzeAndMatchResponse, MatchRequest
from backend.app.services.resume_service import ResumeService

router = APIRouter(prefix=get_settings().api_prefix)


def get_resume_service() -> ResumeService:
    return ResumeService(get_settings())


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "ai_provider": settings.ai_provider,
        "ai_model": settings.resolved_ai_model,
        "ai_enabled": bool(settings.resolved_ai_api_key),
    }


@router.post("/resumes/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    force_refresh: bool = Form(False),
    service: ResumeService = Depends(get_resume_service),
):
    return await service.analyze_upload(file, force_refresh=force_refresh)


@router.post("/resumes/{resume_id}/match")
async def match_resume(
    resume_id: str,
    request: MatchRequest,
    force_refresh: bool = False,
    service: ResumeService = Depends(get_resume_service),
):
    return await service.match_resume(
        resume_id=resume_id,
        job_description=request.job_description,
        force_refresh=force_refresh,
    )


@router.post("/resumes/analyze-and-match")
async def analyze_and_match(
    file: UploadFile = File(...),
    job_description: str | None = Form(None),
    force_refresh: bool = Form(False),
    service: ResumeService = Depends(get_resume_service),
):
    return await service.analyze_and_match_upload(
        file,
        job_description=job_description,
        force_refresh=force_refresh,
    )
