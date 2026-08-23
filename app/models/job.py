from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class WorkplaceType(str, Enum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "On-site"
    UNKNOWN = "Unknown"


class EmploymentType(str, Enum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"
    UNKNOWN = "Unknown"


class ExtractedJobDescription(BaseModel):
    """Structured representation of a parsed game developer job description."""
    title: str = Field(..., description="Standardized job title")
    company: str = Field(..., description="Hiring company or game studio name")
    location: str = Field(default="Unknown", description="Job location (city/country or remote)")
    workplace_type: WorkplaceType = Field(default=WorkplaceType.UNKNOWN)
    employment_type: EmploymentType = Field(default=EmploymentType.FULL_TIME)

    # Compensation & Seniority
    salary_min: Optional[float] = Field(None, description="Minimum annual salary if disclosed")
    salary_max: Optional[float] = Field(None, description="Maximum annual salary if disclosed")
    salary_currency: Optional[str] = Field(None, description="Salary currency (USD, EUR, GBP, INR, etc.)")
    experience_years_min: Optional[int] = Field(None, description="Minimum required years of experience")
    experience_years_max: Optional[int] = Field(None, description="Maximum experience if specified")

    # Tech Stack & Domain
    primary_engines: List[str] = Field(default_factory=list, description="Primary engines required (e.g. Unity, Unreal)")
    secondary_engines: List[str] = Field(default_factory=list, description="Secondary or preferred engines")
    primary_languages: List[str] = Field(default_factory=list, description="Primary languages (e.g. C#, C++, Python)")
    secondary_languages: List[str] = Field(default_factory=list, description="Secondary or optional languages")
    game_systems: List[str] = Field(
        default_factory=list,
        description="Key game systems emphasized (e.g. AI / Behavior Trees, Gameplay Mechanics, UI / Tools, Physics, Multiplayer / Netcode, Shaders / Graphics)"
    )
    platforms: List[str] = Field(default_factory=list, description="Target platforms (PC, Console, Mobile, VR/AR, WebGL)")

    # Breakdown of details
    responsibilities: List[str] = Field(default_factory=list, description="Core responsibilities extracted from the JD")
    hard_requirements: List[str] = Field(default_factory=list, description="Mandatory qualifications / prerequisites")
    preferred_requirements: List[str] = Field(default_factory=list, description="Nice-to-have qualifications")
    tech_stack: List[str] = Field(default_factory=list, description="All specific tools/libraries/frameworks mentioned")

    # Logistics
    visa_sponsorship: Optional[bool] = Field(None, description="True if sponsorship is offered, False if strictly disallowed, None if unstated")
    application_url: Optional[str] = Field(None, description="Direct URL to apply")
    raw_source: Optional[str] = Field(None, description="Original raw text or markdown of the JD")


class CategoryScore(BaseModel):
    category_name: str
    max_points: float
    awarded_points: float
    reason: str
    matched_items: List[str] = Field(default_factory=list)
    missing_items: List[str] = Field(default_factory=list)


class MatchScoreBreakdown(BaseModel):
    """Detailed score report comparing a JD against the Candidate Profile."""
    total_score: float = Field(..., description="Overall calculated match score (0 - 100)")
    meets_hard_requirements: bool = Field(default=True, description="True if no hard disqualifiers were triggered")
    disqualification_reasons: List[str] = Field(default_factory=list, description="Reasons for immediate disqualification if any")

    # Granular scoring
    category_scores: Dict[str, CategoryScore] = Field(default_factory=dict)

    # Qualitative analysis
    key_strengths: List[str] = Field(default_factory=list, description="Candidate advantages for this specific role")
    key_gaps: List[str] = Field(default_factory=list, description="Missing skills or experience gaps")
    match_summary: str = Field(..., description="Concise overview of candidate suitability")

    # Decisions
    recommended_action: str = Field(..., description="AUTO_APPLY, REVIEW_QUEUE, REJECT, or REQUIRES_HUMAN")
    recommended_resume_filename: Optional[str] = Field(None, description="Filename of the best matching resume variant")
