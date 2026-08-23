import os
from pathlib import Path
import pytest
from app.models.application import ApplicationRecord, ApplicationStatus
from app.services.excel_tracker import ExcelTracker


@pytest.fixture
def temp_excel_tracker(tmp_path: Path) -> ExcelTracker:
    tracker_file = tmp_path / "test_tracker.xlsx"
    return ExcelTracker(file_path=tracker_file, auto_backup=True)


def test_excel_tracker_initialization(temp_excel_tracker: ExcelTracker):
    info = temp_excel_tracker.inspect_workbook()
    assert info["active_sheet"] == "Applications"
    assert len(info["headers"]) >= 10
    assert "Company" in info["headers"]
    assert "Job Title" in info["headers"]
    assert "Status" in info["headers"]


def test_excel_tracker_upsert_and_deduplication(temp_excel_tracker: ExcelTracker):
    app = ApplicationRecord(
        application_id="APP-TEST-001",
        company="Nintendo Studios",
        job_title="Unity Gameplay Programmer",
        location="Remote",
        match_score=92.5,
        status=ApplicationStatus.READY,
        resume_used="unity_gameplay.pdf",
        job_url="https://example.com/jobs/001"
    )

    # 1. Insert new application
    action1, row1 = temp_excel_tracker.upsert_application(app)
    assert action1 == "CREATED"
    assert row1 == 2

    # Verify data in sheet
    apps = temp_excel_tracker.get_all_applications()
    assert len(apps) == 1
    assert apps[0]["company"] == "Nintendo Studios"
    assert apps[0]["status"] == "READY"

    # 2. Update status of the same application
    app.status = ApplicationStatus.APPLIED
    action2, row2 = temp_excel_tracker.upsert_application(app)
    assert action2 == "UPDATED"
    assert row2 == 2  # Must update existing row, not append duplicate

    apps_updated = temp_excel_tracker.get_all_applications()
    assert len(apps_updated) == 1
    assert apps_updated[0]["status"] == "APPLIED"
