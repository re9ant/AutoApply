import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel

from app.ai.client import ai_client
from app.ai.providers import LLMProviderType, ProviderConfig
from app.config.settings import settings
from app.models.application import ApplicationRecord, ApplicationStatus
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, MatchScoreBreakdown
from app.scrapers.discovery_service import (
    discovery_service,
    DiscoveryRequest,
    DiscoveryResponse,
    POPULAR_STUDIO_PRESETS
)
from app.services.application_service import application_service
from app.services.excel_tracker import excel_tracker
from app.services.profile_loader import profile_loader
from app.services.resume_selector import resume_selector, ResumeVariant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# --- DTOs ---
class AnalyzeJDRequest(BaseModel):
    raw_jd_text: str
    job_url: Optional[str] = None
    application_url: Optional[str] = None
    source: str = "Direct / Manual"
    sync_to_excel: bool = True


class AnalyzeJDResponse(BaseModel):
    application_id: str
    extracted_jd: ExtractedJobDescription
    score_breakdown: MatchScoreBreakdown
    status: str
    recommended_resume: str
    excel_synced: bool


class AIConfigUpdateRequest(BaseModel):
    provider_type: LLMProviderType
    api_key: Optional[str] = None
    model: str
    base_url: Optional[str] = None
    temperature: float = 0.1


class UpdateStatusRequest(BaseModel):
    status: ApplicationStatus
    notes: Optional[str] = None


# --- 1. Candidate Profile Endpoints ---
@router.get("/profile", response_model=CandidateProfile)
async def get_profile():
    try:
        return profile_loader.load_profile(force_reload=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile")
async def save_profile(profile: CandidateProfile):
    try:
        profile_path = settings.resolve_path(settings.CANDIDATE_PROFILE_PATH)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))
        profile_loader.load_profile(force_reload=True)
        return {"success": True, "message": "Candidate profile updated successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {e}")


# --- 2. JD Analysis & Matching Endpoint ---
@router.post("/analyze-jd", response_model=AnalyzeJDResponse)
async def analyze_jd(req: AnalyzeJDRequest):
    try:
        app_record, score = await application_service.process_job_posting(
            raw_jd_text=req.raw_jd_text,
            job_url=req.job_url,
            application_url=req.application_url,
            source=req.source
        )

        extracted = ExtractedJobDescription.model_validate(app_record.structured_jd)

        return AnalyzeJDResponse(
            application_id=app_record.application_id,
            extracted_jd=extracted,
            score_breakdown=score,
            status=app_record.status.value,
            recommended_resume=score.recommended_resume_filename or "general_game_programmer.pdf",
            excel_synced=req.sync_to_excel
        )
    except Exception as e:
        logger.error(f"JD Analysis endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing job description: {e}")


# --- 3. Job Discovery & Scraping Endpoints ---
@router.get("/discovery/presets")
async def get_discovery_presets():
    return POPULAR_STUDIO_PRESETS


@router.post("/discovery/scrape", response_model=DiscoveryResponse)
async def run_job_discovery(request: DiscoveryRequest):
    try:
        response = await discovery_service.run_discovery(request)
        return response
    except Exception as e:
        logger.error(f"Job discovery error: {e}")
        raise HTTPException(status_code=500, detail=f"Job discovery failed: {e}")


# --- 4. Resume Management Endpoints ---
@router.get("/resumes", response_model=List[ResumeVariant])
async def get_resumes():
    return resume_selector.get_all_variants()


@router.post("/resumes")
async def save_resumes(variants: List[ResumeVariant]):
    try:
        index_path = settings.resolve_path(settings.RESUMES_DIR / "index.json")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in variants], f, indent=2)
        resume_selector._load_variants()
        return {"success": True, "message": "Resume registry updated successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resumes/add")
async def add_resume_variant(variant: ResumeVariant):
    try:
        variants = resume_selector.get_all_variants()
        # Update existing or append new
        updated = [v for v in variants if v.filename.lower() != variant.filename.lower()]
        updated.append(variant)

        index_path = settings.resolve_path(settings.RESUMES_DIR / "index.json")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in updated], f, indent=2)

        resume_selector._load_variants()
        return {"success": True, "message": f"Resume '{variant.title}' added successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add resume variant: {e}")


@router.post("/resumes/upload")
async def upload_resume_file(file: UploadFile = File(...)):
    try:
        resumes_dir = settings.resolve_path(settings.RESUMES_DIR)
        resumes_dir.mkdir(parents=True, exist_ok=True)
        file_path = resumes_dir / file.filename

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "success": True,
            "filename": file.filename,
            "message": f"File '{file.filename}' uploaded successfully to {resumes_dir}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")


@router.delete("/resumes/{filename}")
async def delete_resume_variant(filename: str):
    try:
        variants = resume_selector.get_all_variants()
        updated = [v for v in variants if v.filename.lower() != filename.lower()]

        index_path = settings.resolve_path(settings.RESUMES_DIR / "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in updated], f, indent=2)

        resume_selector._load_variants()
        return {"success": True, "message": f"Resume '{filename}' removed from registry."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 5. Application Tracker Endpoints ---
@router.get("/applications")
async def get_applications():
    try:
        excel_apps = excel_tracker.get_all_applications()
        return {
            "total": len(excel_apps),
            "applications": excel_apps,
            "metadata": excel_tracker.inspect_workbook()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/applications/update-status")
async def update_application_status(app_id: str, req: UpdateStatusRequest):
    try:
        app = ApplicationRecord(
            application_id=app_id,
            company="",
            job_title="",
            status=req.status,
            notes=req.notes
        )
        action, row = excel_tracker.upsert_application(app)
        return {"success": True, "action": action, "row": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 6. AI Settings & Connectivity Endpoints ---
@router.get("/settings/ai")
async def get_ai_settings():
    cfg = ai_client.config
    return {
        "provider_type": cfg.provider_type.value,
        "model": cfg.model,
        "base_url": cfg.base_url or "",
        "temperature": cfg.temperature,
        "has_api_key": bool(cfg.api_key),
        "is_available": ai_client.is_available
    }


@router.post("/settings/ai")
async def update_ai_settings(req: AIConfigUpdateRequest):
    try:
        new_config = ProviderConfig(
            provider_type=req.provider_type,
            api_key=req.api_key if req.api_key else ai_client.config.api_key,
            model=req.model,
            base_url=req.base_url if req.base_url else None,
            temperature=req.temperature
        )
        ai_client.set_config(new_config)
        return {"success": True, "message": "AI settings updated successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/ai/test")
async def test_ai_connection():
    result = await ai_client.test_connection()
    return result
