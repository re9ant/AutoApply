from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class ContactInfo(BaseModel):
    name: str = Field(..., description="Full candidate name")
    email: EmailStr = Field(..., description="Primary contact email")
    phone: Optional[str] = Field(None, description="Contact phone number with country code")
    location: str = Field(..., description="Current residence (City, State/Province, Country)")
    portfolio: Optional[str] = Field(None, description="Portfolio website or personal website URL")
    github: Optional[str] = Field(None, description="GitHub profile URL")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    itch_io: Optional[str] = Field(None, description="itch.io or demo showcase URL")
    artstation: Optional[str] = Field(None, description="ArtStation or technical showcase URL")


class WorkAuthorization(BaseModel):
    citizenship: List[str] = Field(default_factory=list, description="Countries of citizenship")
    authorized_countries: List[str] = Field(default_factory=list, description="Countries authorized to work without sponsorship")
    requires_sponsorship: bool = Field(default=False, description="Whether candidate requires visa sponsorship")
    willing_to_relocate: bool = Field(default=True, description="Willingness to relocate for on-site/hybrid positions")


class Education(BaseModel):
    institution: str = Field(..., description="University or college name")
    degree: str = Field(..., description="Degree type (e.g., B.Tech, B.S., M.S.)")
    field_of_study: str = Field(..., description="Major/field of study (e.g., Computer Science and Engineering)")
    start_year: Optional[int] = None
    graduation_year: int = Field(..., description="Year of graduation")
    gpa: Optional[str] = Field(None, description="GPA or grade percentage if applicable")
    relevant_coursework: List[str] = Field(default_factory=list, description="Relevant coursework subjects")


class SkillsTaxonomy(BaseModel):
    domains: List[str] = Field(
        default_factory=lambda: [
            "Game Development",
            "Backend Engineering",
            "Full-Stack Development",
            "Systems Programming"
        ],
        description="Candidate's engineering domains"
    )
    languages: List[str] = Field(default_factory=list, description="Programming languages (e.g. C#, C++, Python, TypeScript, Go, Rust, SQL)")
    engines: List[str] = Field(default_factory=list, description="Game engines (e.g. Unity, Unreal Engine, Godot)")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks and libraries (e.g. FastAPI, React, Next.js, Django, PyTorch, Unity DOTS)")
    tools: List[str] = Field(default_factory=list, description="Tools, databases, and DevOps (e.g. Git, Docker, PostgreSQL, Redis, AWS, Linux)")
    game_systems: List[str] = Field(default_factory=list, description="Specialized game subsystems (e.g. Gameplay Mechanics, AI/Behavior Trees, UI Toolkit, Physics, Netcode)")


class ExperienceItem(BaseModel):
    company: str = Field(..., description="Company or studio name")
    role: str = Field(..., description="Job title / role")
    location: Optional[str] = None
    employment_type: str = Field(default="Full-time", description="Full-time, Contract, Internship, Indie")
    start_date: str = Field(..., description="Start date (YYYY-MM or YYYY)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM or YYYY) or 'Present'")
    is_current: bool = Field(default=False)
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list, description="Key contributions and achievements")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")


class ProjectItem(BaseModel):
    name: str = Field(..., description="Project or game title")
    domain: Optional[str] = Field(None, description="Domain / category (e.g., Game Development, Backend API, Web App)")
    role: str = Field(..., description="Candidate's role in the project")
    engine: Optional[str] = Field(None, description="Game engine or primary framework used")
    description: str = Field(..., description="Project overview")
    technical_highlights: List[str] = Field(default_factory=list, description="Deep-dive technical systems built")
    technologies: List[str] = Field(default_factory=list, description="Languages and tools used")
    repo_url: Optional[str] = None
    demo_url: Optional[str] = None


class Achievement(BaseModel):
    title: str = Field(..., description="Award, hackathon, game jam, or certification title")
    issuer: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None


class JobPreferences(BaseModel):
    roles: List[str] = Field(
        default_factory=lambda: [
            "Gameplay Programmer",
            "Unity Developer",
            "Game Programmer",
            "Software Engineer",
            "Backend Developer",
            "Full Stack Developer",
            "Junior Game Developer",
            "Unity Tools Programmer"
        ],
        description="Target job titles across tech roles"
    )
    locations: List[str] = Field(default_factory=list, description="Target cities or regions")
    remote_only: bool = Field(default=False)
    allow_hybrid: bool = Field(default=True)
    allow_onsite: bool = Field(default=True)
    minimum_match_score: int = Field(default=75, description="Threshold score to trigger application preparation")
    salary_currency: str = Field(default="USD")
    minimum_salary: Optional[int] = Field(None, description="Minimum acceptable annual salary")


class CandidateProfile(BaseModel):
    """The master Candidate Profile schema — source of truth for the autonomous application agent."""
    candidate: ContactInfo
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    education: List[Education] = Field(default_factory=list)
    skills: SkillsTaxonomy = Field(default_factory=SkillsTaxonomy)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    preferences: JobPreferences = Field(default_factory=JobPreferences)
