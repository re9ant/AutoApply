import pytest
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, WorkplaceType, EmploymentType
from app.services.job_scorer import JobScorer
from app.services.profile_loader import profile_loader
from app.services.resume_selector import ResumeSelector


@pytest.fixture
def candidate_profile() -> CandidateProfile:
    return profile_loader.load_profile(force_reload=True)


@pytest.fixture
def scorer() -> JobScorer:
    return JobScorer(min_auto_apply_score=75, min_review_score=60)


def test_backend_python_fastapi_matching(candidate_profile, scorer):
    backend_jd = ExtractedJobDescription(
        title="Backend Software Engineer",
        company="Streamline Cloud",
        location="Remote",
        workplace_type=WorkplaceType.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        experience_years_min=1,
        primary_languages=["Python", "SQL"],
        tech_stack=["FastAPI", "PostgreSQL", "Docker", "Redis"],
        responsibilities=["Develop low-latency APIs and event pipelines in FastAPI."],
        hard_requirements=["1+ years Python FastAPI experience"]
    )

    breakdown = scorer.calculate_match(backend_jd, candidate_profile)

    # Candidate has Python, FastAPI, PostgreSQL, Docker, Redis
    assert breakdown.total_score >= 80.0
    assert breakdown.recommended_action == "AUTO_APPLY"

    # Verify resume selector chooses Backend resume
    selector = ResumeSelector()
    best_resume = selector.select_best_resume(backend_jd)
    assert best_resume == "backend_software_engineer.pdf"


def test_fullstack_typescript_matching(candidate_profile, scorer):
    fullstack_jd = ExtractedJobDescription(
        title="Full Stack Developer",
        company="Nexus Web Studio",
        location="San Francisco, CA",
        workplace_type=WorkplaceType.HYBRID,
        employment_type=EmploymentType.FULL_TIME,
        experience_years_min=1,
        primary_languages=["TypeScript", "JavaScript"],
        tech_stack=["React", "Next.js", "Tailwind CSS"],
        responsibilities=["Build responsive React interfaces and web APIs."],
        hard_requirements=["Proficiency in React and TypeScript"]
    )

    breakdown = scorer.calculate_match(fullstack_jd, candidate_profile)

    assert breakdown.total_score >= 75.0

    # Verify resume selector chooses Fullstack resume
    selector = ResumeSelector()
    best_resume = selector.select_best_resume(fullstack_jd)
    assert best_resume == "fullstack_developer.pdf"
