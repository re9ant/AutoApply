import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
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


class ResumeSaveRequest(BaseModel):
    original_filename: Optional[str] = None
    variant: ResumeVariant


@router.post("/resumes/save")
async def save_resume_variant(req: ResumeSaveRequest):
    try:
        variants = resume_selector.get_all_variants()
        target_name = (req.original_filename or req.variant.filename).lower()
        updated = [v for v in variants if v.filename.lower() != target_name]
        updated.append(req.variant)

        index_path = settings.resolve_path(settings.RESUMES_DIR / "index.json")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in updated], f, indent=2)

        resume_selector._load_variants()
        return {"success": True, "message": f"Resume variant '{req.variant.title}' saved successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume variant: {e}")


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


@router.get("/resumes/view/{filename}")
async def view_resume_file(filename: str):
    try:
        resumes_dir = settings.resolve_path(settings.RESUMES_DIR)
        file_path = resumes_dir / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Resume file '{filename}' not found on server.")

        media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# --- 5. Application & Batch Apply Endpoints ---
class BatchApplyItem(BaseModel):
    application_id: Optional[str] = None
    company: str
    job_title: str
    job_url: Optional[str] = None
    application_url: Optional[str] = None
    location: Optional[str] = "Unknown"
    resume_used: Optional[str] = None
    notes: Optional[str] = None


class BatchApplyRequest(BaseModel):
    items: List[BatchApplyItem]
    prefer_email: bool = True
    is_dry_run: bool = True


@router.post("/applications/apply-batch")
async def apply_batch(req: BatchApplyRequest):
    try:
        results = []
        for item in req.items:
            app = ApplicationRecord(
                application_id=item.application_id or f"APP-{item.company[:4].upper()}-{item.job_title[:4].upper()}",
                company=item.company,
                job_title=item.job_title,
                job_url=item.job_url,
                application_url=item.application_url or item.job_url,
                location=item.location,
                resume_used=item.resume_used,
                notes=item.notes
            )
            res = await application_service.apply_to_job(
                app=app,
                prefer_email=req.prefer_email,
                is_dry_run=req.is_dry_run
            )
            results.append(res)
        return {
            "success": True,
            "count": len(results),
            "is_dry_run": req.is_dry_run,
            "results": results
        }
    except Exception as e:
        logger.error(f"Batch apply failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        "api_key": cfg.api_key or "",
        "temperature": cfg.temperature,
        "has_api_key": bool(cfg.api_key),
        "is_available": ai_client.is_available
    }


@router.post("/settings/ai")
async def update_ai_settings(req: AIConfigUpdateRequest):
    try:
        model = req.model
        base_url = req.base_url if req.base_url else None

        if req.provider_type == LLMProviderType.GEMINI:
            if not base_url or "generativelanguage" not in base_url:
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            if not model or "gpt-" in model.lower():
                model = "gemini-1.5-flash"

        new_config = ProviderConfig(
            provider_type=req.provider_type,
            api_key=req.api_key if req.api_key else ai_client.config.api_key,
            model=model,
            base_url=base_url,
            temperature=req.temperature
        )
        ai_client.set_config(new_config)
        return {"success": True, "message": "AI settings saved and persisted successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/ai/test")
async def test_ai_connection():
    result = await ai_client.test_connection()
    return result


# --- 7. Email / Gmail Settings Endpoints ---
class EmailSettingsRequest(BaseModel):
    email_address: str
    app_password: str
    display_name: Optional[str] = None


@router.get("/settings/email")
async def get_email_settings():
    from app.services.email_service import email_service
    return {
        "email_address": email_service.config.email_address or "",
        "app_password": email_service.config.app_password or "",
        "has_password": bool(email_service.config.app_password),
        "display_name": email_service.config.display_name or "",
        "smtp_host": email_service.config.smtp_host,
        "smtp_port": email_service.config.smtp_port
    }


@router.post("/settings/email")
async def update_email_settings(req: EmailSettingsRequest):
    try:
        from app.services.email_service import email_service, EmailAccountConfig
        new_config = EmailAccountConfig(
            email_address=req.email_address,
            app_password=req.app_password,
            display_name=req.display_name
        )
        email_service.set_config(new_config)
        return {"success": True, "message": f"Gmail account '{req.email_address}' configured successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/email/test")
async def test_email_settings():
    from app.services.email_service import email_service
    return email_service.test_smtp_connection()


@router.get("/settings/discovery")
async def get_discovery_settings():
    from app.config.config_store import config_store
    return config_store.get_discovery_config()


@router.post("/settings/discovery")
async def save_discovery_settings(data: Dict[str, Any]):
    from app.config.config_store import config_store
    config_store.set_discovery_config(data)
    return {"success": True, "message": "Discovery settings persisted."}


@router.get("/settings/preferences")
async def get_apply_preferences():
    from app.config.config_store import config_store
    return config_store.get_apply_preferences()


@router.post("/settings/preferences")
async def save_apply_preferences(data: Dict[str, Any]):
    from app.config.config_store import config_store
    config_store.set_apply_preferences(data)
    return {"success": True, "message": "Apply preferences persisted."}


# --- 8. Email Draft Generation & Sending ---
class DraftItem(BaseModel):
    company: str
    job_title: str
    job_url: Optional[str] = None
    hr_email: Optional[str] = None
    resume_used: Optional[str] = None
    notes: Optional[str] = None
    location: Optional[str] = "Remote"


class EditedDraft(BaseModel):
    company: str
    job_title: str
    job_url: Optional[str] = None
    to_email: str
    subject: str
    body_text: str
    resume_used: str
    is_dry_run: bool = True


class GenerateDraftsRequest(BaseModel):
    items: List[DraftItem]
    is_dry_run: bool = True


class SendDraftsRequest(BaseModel):
    drafts: List[EditedDraft]
    is_dry_run: bool = True


@router.post("/applications/generate-drafts")
async def generate_drafts(req: GenerateDraftsRequest):
    """Generate email drafts for review — does NOT send anything."""
    try:
        from app.services.email_service import email_service
        from app.services.profile_loader import profile_loader
        from app.models.job import ExtractedJobDescription, MatchScoreBreakdown
        from app.services.resume_selector import resume_selector

        profile = profile_loader.load_profile()
        drafts = []
        for item in req.items:
            try:
                # Build a minimal JD object for email generation
                jd = ExtractedJobDescription(
                    title=item.job_title,
                    company=item.company,
                    location=item.location or "Remote",
                    application_url=item.job_url or "",
                    raw_source=item.notes or f"{item.job_title} at {item.company}"
                )
                resume_fn = item.resume_used
                if not resume_fn:
                    variants = resume_selector.get_all_variants()
                    resume_fn = variants[0].filename if variants else "resume.pdf"

                # Score placeholder for email generation
                score = MatchScoreBreakdown(
                    total_score=75,
                    key_strengths=["Relevant experience", "Technical match"],
                    recommended_resume_filename=resume_fn
                )

                gen = email_service.generate_application_email(
                    jd=jd,
                    profile=profile,
                    score=score,
                    resume_filename=resume_fn,
                    recipient_override=item.hr_email or None,
                    is_dry_run=req.is_dry_run
                )

                drafts.append({
                    "company": item.company,
                    "job_title": item.job_title,
                    "job_url": item.job_url or "",
                    "to_email": gen.recipient_email,
                    "subject": gen.subject,
                    "body_text": gen.body_text,
                    "resume_used": resume_fn,
                    "attachment_found": gen.attachment_found,
                    "is_dry_run": req.is_dry_run
                })
            except Exception as e:
                logger.error(f"Draft generation error for {item.company}: {e}")
                drafts.append({
                    "company": item.company,
                    "job_title": item.job_title,
                    "job_url": item.job_url or "",
                    "to_email": item.hr_email or "",
                    "subject": f"Application: {item.job_title}",
                    "body_text": "",
                    "resume_used": item.resume_used or "",
                    "attachment_found": False,
                    "is_dry_run": req.is_dry_run,
                    "error": str(e)
                })

        return {"success": True, "count": len(drafts), "drafts": drafts}
    except Exception as e:
        logger.error(f"Generate drafts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/applications/send-drafts")
async def send_drafts(req: SendDraftsRequest):
    """Send user-reviewed and edited email drafts, then log to Sent Emails Excel sheet."""
    try:
        from app.services.email_service import email_service, GeneratedEmail

        results = []
        for draft in req.drafts:
            try:
                email_data = GeneratedEmail(
                    recipient_email=draft.to_email,
                    subject=draft.subject,
                    body_text=draft.body_text,
                    attached_resume_filename=draft.resume_used,
                    attachment_found=True,
                    is_dry_run=draft.is_dry_run
                )

                success, detail = email_service.send_application_email(email_data)
                status_str = "Dry Run" if draft.is_dry_run else ("Sent" if success else "Failed")

                # Log to Excel Sent Emails sheet
                excel_tracker.log_sent_email(
                    company=draft.company,
                    job_title=draft.job_title,
                    recipient_email=draft.to_email,
                    subject=draft.subject,
                    resume_filename=draft.resume_used,
                    body_text=draft.body_text,
                    status=status_str
                )

                results.append({
                    "company": draft.company,
                    "job_title": draft.job_title,
                    "to_email": draft.to_email,
                    "success": success,
                    "status": status_str,
                    "detail": detail
                })
            except Exception as e:
                logger.error(f"Failed to send draft for {draft.company}: {e}")
                results.append({
                    "company": draft.company,
                    "job_title": draft.job_title,
                    "to_email": draft.to_email,
                    "success": False,
                    "status": "Failed",
                    "detail": str(e)
                })

        return {"success": True, "count": len(results), "results": results}
    except Exception as e:
        logger.error(f"Send drafts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discovery/rescan-email")
async def rescan_email(company: str, job_url: str = "", description_text: str = ""):
    """Re-scan a company website to find HR email. Called by 'Try Again' button on job cards."""
    try:
        from app.services.email_finder import email_finder
        found = await email_finder.find_email(
            job_url=job_url or None,
            company=company,
            description_text=description_text or None
        )
        return {
            "email": found,
            "status": "FOUND" if found else "NOT_FOUND"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emails/sent")
async def get_sent_emails():
    """Return all rows from the Sent Emails sheet in tracker.xlsx."""
    try:
        sent = excel_tracker.get_sent_emails()
        return {"total": len(sent), "emails": sent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
