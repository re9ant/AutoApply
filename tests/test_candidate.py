import pytest
from app.models.candidate import CandidateProfile
from app.services.profile_loader import ProfileLoader


def test_candidate_profile_loader():
    loader = ProfileLoader()
    profile = loader.load_profile(force_reload=True)

    assert profile.candidate.name is not None
    assert "@" in profile.candidate.email
    assert "Unity (2021/2022/6)" in profile.skills.engines or "Unity" in str(profile.skills.engines)
    assert "C#" in profile.skills.languages
    assert "Python" in profile.skills.languages
    assert len(profile.education) >= 1
    assert len(profile.projects) >= 1
    assert len(profile.experience) >= 1


def test_candidate_skills_structure():
    loader = ProfileLoader()
    profile = loader.load_profile(force_reload=True)

    # Verify game dev & general tech taxonomy
    assert any("Gameplay" in s for s in profile.skills.game_systems)
    assert any("AI" in s for s in profile.skills.game_systems)
    assert len(profile.skills.languages) >= 1
    assert profile.preferences.minimum_match_score == 75
