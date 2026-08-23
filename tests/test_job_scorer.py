import pytest
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, WorkplaceType, EmploymentType
from app.services.job_scorer import JobScorer
from app.services.profile_loader import profile_loader


@pytest.fixture
def candidate_profile() -> CandidateProfile:
    return profile_loader.load_profile()


@pytest.fixture
def scorer() -> JobScorer:
    return JobScorer(min_auto_apply_score=75, min_review_score=60)


def test_high_match_unity_gameplay_job(candidate_profile, scorer):
    unity_jd = ExtractedJobDescription(
        title="Unity Gameplay Programmer",
        company="Phoenix Studios",
        location="Remote",
        workplace_type=WorkplaceType.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        experience_years_min=1,
        primary_engines=["Unity"],
        primary_languages=["C#"],
        game_systems=["Gameplay Mechanics", "AI / NPC Systems", "UI & Tools"],
        responsibilities=["Develop player mechanics and combat systems in Unity C#."],
        hard_requirements=["1+ years Unity C# experience"]
    )

    breakdown = scorer.calculate_match(unity_jd, candidate_profile)

    assert breakdown.total_score >= 80.0
    assert breakdown.meets_hard_requirements is True
    assert breakdown.recommended_action == "AUTO_APPLY"
    assert "Unity" in str(breakdown.key_strengths)


def test_unreal_exclusive_senior_job_scoring(candidate_profile, scorer):
    # Job requires Unreal Engine 5 and 7 years experience
    unreal_senior_jd = ExtractedJobDescription(
        title="Senior Unreal Engine Core Developer",
        company="Epic Scale Studios",
        location="On-site New York",
        workplace_type=WorkplaceType.ONSITE,
        employment_type=EmploymentType.FULL_TIME,
        experience_years_min=7,
        primary_engines=["Unreal Engine 5"],
        primary_languages=["C++"],
        game_systems=["Rendering & Shaders", "Engine Core"],
        responsibilities=["Modify UE5 source code and rendering pipelines."],
        hard_requirements=["7+ years C++ and UE5 source modification"]
    )

    breakdown = scorer.calculate_match(unreal_senior_jd, candidate_profile)

    # Should trigger disqualifier or score low due to seniority & engine mismatch
    assert breakdown.total_score < 60.0
    assert breakdown.recommended_action == "REJECT"
