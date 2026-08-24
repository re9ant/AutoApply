import pytest
from app.models.job import ExtractedJobDescription, MatchScoreBreakdown, WorkplaceType, EmploymentType
from app.services.email_service import EmailService, EmailAccountConfig
from app.services.profile_loader import profile_loader
from app.services.application_service import application_service
from app.models.application import ApplicationRecord, ApplicationStatus


def test_hr_email_extraction():
    service = EmailService()

    # 1. Direct email in text
    jd_with_email = "Please send your resume to recruiting@awesomegames.com along with portfolio."
    email = service.extract_hr_email(jd_with_email, "Awesome Games")
    assert email == "recruiting@awesomegames.com"

    # 2. Derive from company domain
    jd_no_email = "Join our studio to build AAA combat experiences."
    derived_email = service.extract_hr_email(jd_no_email, "Supercell", "https://supercell.com/careers/gameplay-dev")
    assert "supercell.com" in derived_email


def test_application_email_generation():
    service = EmailService()
    profile = profile_loader.load_profile()

    jd = ExtractedJobDescription(
        title="Unity Gameplay Programmer",
        company="Phoenix Labs",
        location="Remote",
        workplace_type=WorkplaceType.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        primary_languages=["C#"],
        primary_engines=["Unity"],
        raw_source="We need a Unity gameplay engineer with C# and combat mechanics experience."
    )

    score = MatchScoreBreakdown(
        total_score=88.0,
        recommended_action="AUTO_APPLY",
        match_summary="Strong match across Unity and C#",
        key_strengths=["Unity engine proficiency", "Gameplay combat systems"]
    )

    generated = service.generate_application_email(
        jd=jd,
        profile=profile,
        score=score,
        resume_filename="unity_gameplay.pdf",
        is_dry_run=True
    )

    assert "Application for Unity Gameplay Programmer" in generated.subject
    assert profile.candidate.name in generated.subject
    assert profile.candidate.name in generated.body_text
    assert "Phoenix Labs" in generated.body_text
    assert generated.attached_resume_filename == "unity_gameplay.pdf"
    assert generated.is_dry_run is True


@pytest.mark.asyncio
async def test_batch_apply_dry_run():
    app = ApplicationRecord(
        application_id="TEST-APP-001",
        company="Riot Games",
        job_title="Gameplay Software Engineer",
        job_url="https://riotgames.com/careers/123",
        application_url="https://riotgames.com/careers/123",
        location="Remote",
        resume_used="unity_gameplay.pdf"
    )

    result = await application_service.apply_to_job(
        app=app,
        prefer_email=True,
        is_dry_run=True
    )

    assert result["company"] == "Riot Games"
    assert result["is_dry_run"] is True
    assert "Email" in result["method"]
    assert "email_preview" in result
    assert result["email_preview"]["to"] is not None
    assert "Subject" in result["details"]
