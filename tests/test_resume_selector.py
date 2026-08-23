import pytest
from app.models.job import ExtractedJobDescription
from app.services.resume_selector import ResumeSelector


def test_resume_selector_gameplay():
    selector = ResumeSelector()
    jd = ExtractedJobDescription(
        title="Unity Gameplay Programmer",
        company="Action Studio",
        primary_engines=["Unity"],
        primary_languages=["C#"],
        game_systems=["Combat", "Character Controller", "AI"]
    )
    recommended = selector.select_best_resume(jd)
    assert recommended in ["unity_gameplay.pdf", "SaiKowsikAyyalasomayajulaResume.pdf"]


def test_resume_selector_tools():
    selector = ResumeSelector()
    jd = ExtractedJobDescription(
        title="Unity Tools & Pipeline Engineer",
        company="Tooling Games",
        primary_engines=["Unity"],
        primary_languages=["C#"],
        game_systems=["UI Toolkit", "Editor Scripting", "Custom Inspectors"]
    )
    recommended = selector.select_best_resume(jd)
    assert recommended == "unity_tools.pdf"
