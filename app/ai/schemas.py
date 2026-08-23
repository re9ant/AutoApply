from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.job import WorkplaceType, EmploymentType


class JDExtractionResponse(BaseModel):
    """Schema for OpenAI structured output when parsing raw job descriptions."""
    title: str = Field(..., description="Official job title")
    company: str = Field(..., description="Hiring company or studio name")
    location: str = Field(default="Unknown", description="Job location (City, Country or Remote)")
    workplace_type: WorkplaceType = Field(
        default=WorkplaceType.UNKNOWN,
        description="Remote, Hybrid, On-site, or Unknown"
    )
    employment_type: EmploymentType = Field(
        default=EmploymentType.FULL_TIME,
        description="Full-time, Contract, Internship, etc."
    )
    salary_min: Optional[float] = Field(None, description="Minimum salary if stated")
    salary_max: Optional[float] = Field(None, description="Maximum salary if stated")
    salary_currency: Optional[str] = Field(None, description="Currency abbreviation (e.g. USD, EUR)")
    experience_years_min: Optional[int] = Field(None, description="Minimum years of experience required (e.g. 0 for entry/associate, 2 for mid, etc.)")
    experience_years_max: Optional[int] = Field(None, description="Maximum years if stated")

    primary_engines: List[str] = Field(default_factory=list, description="Primary game engines explicitly required (e.g. ['Unity'])")
    secondary_engines: List[str] = Field(default_factory=list, description="Secondary or bonus game engines (e.g. ['Unreal Engine'])")
    primary_languages: List[str] = Field(default_factory=list, description="Primary programming languages (e.g. ['C#'])")
    secondary_languages: List[str] = Field(default_factory=list, description="Secondary languages (e.g. ['C++', 'Python'])")

    game_systems: List[str] = Field(
        default_factory=list,
        description="Core game systems emphasized (e.g. ['Gameplay Mechanics', 'AI / NPC', 'UI / Tools', 'Physics', 'Networking'])"
    )
    platforms: List[str] = Field(default_factory=list, description="Target platforms (e.g. ['PC', 'Console', 'Mobile', 'VR'])")

    responsibilities: List[str] = Field(default_factory=list, description="Core responsibilities extracted from the posting")
    hard_requirements: List[str] = Field(default_factory=list, description="Strict mandatory prerequisites")
    preferred_requirements: List[str] = Field(default_factory=list, description="Bonus / preferred qualifications")
    tech_stack: List[str] = Field(default_factory=list, description="All tools, libraries, or SDKs mentioned")

    visa_sponsorship: Optional[bool] = Field(None, description="True if sponsorship mentioned as available, False if disallowed, None if unstated")
    application_url: Optional[str] = Field(None, description="Application link if present in JD text")


class QualitativeFitEvaluation(BaseModel):
    """Schema for LLM qualitative semantic fit analysis comparing profile against JD."""
    role_fit_analysis: str = Field(..., description="Detailed evaluation of candidate's background against the role requirements")
    key_strengths: List[str] = Field(default_factory=list, description="Specific candidate strengths and matching experiences")
    key_gaps: List[str] = Field(default_factory=list, description="Specific missing skills or experience gaps")
    semantic_score_adjustment: float = Field(
        default=0.0,
        description="Semantic bonus/penalty points from -10 to +10 based on project depth and portfolio relevance"
    )
    truthfulness_check_passed: bool = Field(
        default=True,
        description="True if candidate claims are grounded in verified profile without assuming fabricated experience"
    )
    summary: str = Field(..., description="High-level 2-3 sentence executive summary of candidate suitability")
