import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Autonomous Job Agent" in response.text
    assert "JD Analyzer" in response.text
    assert "Job Scraper" in response.text


def test_get_profile_api():
    response = client.get("/api/profile")
    assert response.status_code == 200
    data = response.json()
    assert "candidate" in data
    assert "skills" in data
    assert data["candidate"]["name"] is not None


def test_get_resumes_api():
    response = client.get("/api/resumes")
    assert response.status_code == 200
    resumes = response.json()
    assert len(resumes) >= 3
    assert any(r["filename"] == "unity_gameplay.pdf" for r in resumes)


def test_add_and_delete_resume_variant():
    new_variant = {
        "filename": "test_mobile_game_dev.pdf",
        "title": "Mobile Game Developer Resume",
        "domain": "Game Development",
        "primary_engine": "Unity",
        "focus_areas": ["mobile", "android", "ios", "optimization", "c#"],
        "target_roles": ["Mobile Game Developer", "Unity Mobile Engineer"],
        "priority_score": 9
    }

    # Add variant
    add_resp = client.post("/api/resumes/add", json=new_variant)
    assert add_resp.status_code == 200
    assert add_resp.json()["success"] is True

    # Verify present
    res_list = client.get("/api/resumes").json()
    assert any(r["filename"] == "test_mobile_game_dev.pdf" for r in res_list)

    # Delete variant
    del_resp = client.delete("/api/resumes/test_mobile_game_dev.pdf")
    assert del_resp.status_code == 200

    # Verify deleted
    res_list_after = client.get("/api/resumes").json()
    assert not any(r["filename"] == "test_mobile_game_dev.pdf" for r in res_list_after)


def test_upload_resume_file():
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy resume content")
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("test_sample_resume.pdf", dummy_pdf, "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["filename"] == "test_sample_resume.pdf"


def test_view_resume_file():
    # View the uploaded sample PDF
    response = client.get("/api/resumes/view/test_sample_resume.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]


def test_get_and_update_ai_settings_persistence():
    payload = {
        "provider_type": "openai",
        "model": "gpt-4o",
        "api_key": "sk-test-secret-key-12345",
        "base_url": "https://api.openai.com/v1",
        "temperature": 0.2
    }
    post_resp = client.post("/api/settings/ai", json=payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["success"] is True

    get_resp = client.get("/api/settings/ai")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["provider_type"] == "openai"
    assert data["model"] == "gpt-4o"
    assert data["api_key"] == "sk-test-secret-key-12345"


def test_get_and_update_email_settings_persistence():
    payload = {
        "email_address": "applicant.gameplay@gmail.com",
        "app_password": "abcd efgh ijkl mnop",
        "display_name": "Game Dev Applicant"
    }
    post_resp = client.post("/api/settings/email", json=payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["success"] is True

    get_resp = client.get("/api/settings/email")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["email_address"] == "applicant.gameplay@gmail.com"
    assert data["app_password"] == "abcd efgh ijkl mnop"
    assert data["display_name"] == "Game Dev Applicant"
    assert data["has_password"] is True
