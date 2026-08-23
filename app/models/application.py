from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class ApplicationStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    QUEUED = "QUEUED"
    READY = "READY"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    WITHDRAWN = "WITHDRAWN"


class ApplicationRecord(BaseModel):
    """Complete application state tracking data transfer object."""
    application_id: str = Field(default_factory=lambda: f"APP-{uuid.uuid4().hex[:8].upper()}")
    company: str
    job_title: str
    job_url: Optional[str] = None
    application_url: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = "Full-time"
    match_score: Optional[float] = None
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    resume_used: Optional[str] = None
    cover_letter: Optional[str] = None
    source: str = Field(default="Manual / Direct")
    application_method: Optional[str] = Field(default="Email (Gmail)", description="Email (Gmail), Browser (Playwright), or Direct ATS")
    submission_details: Optional[str] = Field(default=None, description="Audit log of exact actions taken during application submission")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    follow_up_date: Optional[str] = None

    # Granular artifacts
    structured_jd: Optional[Dict[str, Any]] = None
    scoring_breakdown: Optional[Dict[str, Any]] = None
    field_answers: Optional[Dict[str, Any]] = None
    human_required_reasons: List[str] = Field(default_factory=list)
