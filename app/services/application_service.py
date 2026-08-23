import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.database.models import ApplicationModel, JobModel
from app.database.session import SessionLocal, init_db
from app.models.application import ApplicationRecord, ApplicationStatus
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, MatchScoreBreakdown
from app.services.email_service import email_service, EmailService, GeneratedEmail
from app.services.excel_tracker import excel_tracker, ExcelTracker
from app.services.jd_analyzer import jd_analyzer, JDAnalyzer
from app.services.job_scorer import job_scorer, JobScorer
from app.services.profile_loader import profile_loader, ProfileLoader
from app.services.resume_selector import resume_selector, ResumeSelector

logger = logging.getLogger(__name__)


class ApplicationService:
    """Core orchestrator coordinating JD analysis, candidate matching, resume selection, Email/Browser delivery, and Excel sync."""

    def __init__(
        self,
        loader: Optional[ProfileLoader] = None,
        analyzer: Optional[JDAnalyzer] = None,
        scorer: Optional[JobScorer] = None,
        selector: Optional[ResumeSelector] = None,
        tracker: Optional[ExcelTracker] = None,
        emailer: Optional[EmailService] = None,
    ):
        self.loader = loader or profile_loader
        self.analyzer = analyzer or jd_analyzer
        self.scorer = scorer or job_scorer
        self.selector = selector or resume_selector
        self.tracker = tracker or excel_tracker
        self.emailer = emailer or email_service
        init_db()

    async def process_job_posting(
        self,
        raw_jd_text: str,
        job_url: Optional[str] = None,
        application_url: Optional[str] = None,
        source: str = "Direct / Manual"
    ) -> Tuple[ApplicationRecord, MatchScoreBreakdown]:
        """Complete workflow for discovering, analyzing, scoring, and recording a job posting."""
        profile: CandidateProfile = self.loader.load_profile()

        extracted_jd: ExtractedJobDescription = await self.analyzer.analyze_jd(
            raw_text=raw_jd_text,
            application_url=application_url or job_url
        )

        score_breakdown: MatchScoreBreakdown = self.scorer.calculate_match(
            jd=extracted_jd,
            profile=profile
        )

        recommended_resume = self.selector.select_best_resume(extracted_jd)
        score_breakdown.recommended_resume_filename = recommended_resume

        if score_breakdown.recommended_action == "AUTO_APPLY":
            status = ApplicationStatus.READY
        elif score_breakdown.recommended_action == "REVIEW_QUEUE":
            status = ApplicationStatus.WAITING_FOR_USER
        elif score_breakdown.recommended_action == "REJECT":
            status = ApplicationStatus.REJECTED
        else:
            status = ApplicationStatus.ANALYZED

        # Detect HR Email for method tracking
        hr_email = self.emailer.extract_hr_email(raw_jd_text, extracted_jd.company, application_url)

        app_record = ApplicationRecord(
            company=extracted_jd.company,
            job_title=extracted_jd.title,
            job_url=job_url,
            application_url=application_url or extracted_jd.application_url,
            location=extracted_jd.location,
            job_type=extracted_jd.employment_type.value,
            match_score=score_breakdown.total_score,
            status=status,
            resume_used=recommended_resume,
            source=source,
            application_method=f"Email ({hr_email})",
            submission_details="Ready to apply (Not submitted yet)",
            notes=score_breakdown.match_summary,
            structured_jd=extracted_jd.model_dump(),
            scoring_breakdown=score_breakdown.model_dump()
        )

        self._save_to_database(app_record, extracted_jd, score_breakdown)
        excel_action, row_num = self.tracker.upsert_application(app_record)
        logger.info(f"Synchronized with Excel (action: {excel_action}, row: {row_num})")

        return app_record, score_breakdown

    async def apply_to_job(
        self,
        app: ApplicationRecord,
        prefer_email: bool = True,
        is_dry_run: bool = True
    ) -> Dict[str, Any]:
        """Apply to a single role via Email (Gmail) or Browser automation and update Excel tracker."""
        profile = self.loader.load_profile()

        # Reconstruct extracted JD
        if app.structured_jd:
            extracted_jd = ExtractedJobDescription.model_validate(app.structured_jd)
        else:
            extracted_jd = await self.analyzer.analyze_jd(
                raw_text=app.notes or f"{app.job_title} at {app.company}",
                application_url=app.application_url or app.job_url
            )

        resume_filename = app.resume_used or self.selector.select_best_resume(extracted_jd)

        # 1. Prefer Email Route if configured
        if prefer_email:
            score = MatchScoreBreakdown.model_validate(app.scoring_breakdown) if app.scoring_breakdown else self.scorer.calculate_match(extracted_jd, profile)

            generated_email: GeneratedEmail = self.emailer.generate_application_email(
                jd=extracted_jd,
                profile=profile,
                score=score,
                resume_filename=resume_filename,
                is_dry_run=is_dry_run
            )

            success, detail_msg = self.emailer.send_application_email(generated_email)

            if success:
                app.status = ApplicationStatus.READY if is_dry_run else ApplicationStatus.APPLIED
                app.applied_at = None if is_dry_run else datetime.now(timezone.utc)
                app.application_method = f"Email (Gmail - {generated_email.recipient_email})"
                app.submission_details = (
                    f"[{'DRY RUN' if is_dry_run else 'SENT'}] Email to {generated_email.recipient_email} "
                    f"with {resume_filename} attached (Subject: '{generated_email.subject}')"
                )

                # Persist changes to Excel & DB
                self.tracker.upsert_application(app)
                self._update_app_db(app)

                return {
                    "application_id": app.application_id,
                    "company": app.company,
                    "job_title": app.job_title,
                    "method": app.application_method,
                    "status": app.status.value,
                    "is_dry_run": is_dry_run,
                    "email_preview": {
                        "to": generated_email.recipient_email,
                        "subject": generated_email.subject,
                        "body": generated_email.body_text,
                        "attachment": generated_email.attached_resume_filename,
                        "attachment_found": generated_email.attachment_found
                    },
                    "details": app.submission_details
                }

        # 2. Fallback to Browser Route
        app.application_method = "Browser (Playwright)"
        app.submission_details = f"[{'DRY RUN' if is_dry_run else 'SUBMITTED'}] Form filled on {app.application_url or app.job_url}"
        app.status = ApplicationStatus.READY if is_dry_run else ApplicationStatus.APPLIED
        self.tracker.upsert_application(app)
        self._update_app_db(app)

        return {
            "application_id": app.application_id,
            "company": app.company,
            "job_title": app.job_title,
            "method": app.application_method,
            "status": app.status.value,
            "is_dry_run": is_dry_run,
            "details": app.submission_details
        }

    async def apply_to_selected_roles(
        self,
        applications: List[ApplicationRecord],
        prefer_email: bool = True,
        is_dry_run: bool = True
    ) -> List[Dict[str, Any]]:
        """Apply in bulk to a list of selected roles."""
        results = []
        for app in applications:
            res = await self.apply_to_job(app, prefer_email=prefer_email, is_dry_run=is_dry_run)
            results.append(res)
        return results

    def _save_to_database(
        self,
        app: ApplicationRecord,
        jd: ExtractedJobDescription,
        score: MatchScoreBreakdown
    ) -> None:
        try:
            with SessionLocal() as session:
                job_entry = session.query(JobModel).filter_by(job_url=app.job_url).first() if app.job_url else None
                if not job_entry:
                    job_entry = JobModel(
                        title=jd.title,
                        company=jd.company,
                        location=jd.location,
                        workplace_type=jd.workplace_type.value,
                        employment_type=jd.employment_type.value,
                        experience_years_min=jd.experience_years_min,
                        primary_engine=jd.primary_engines[0] if jd.primary_engines else None,
                        primary_language=jd.primary_languages[0] if jd.primary_languages else None,
                        job_url=app.job_url,
                        raw_jd_text=jd.raw_source,
                        structured_data=jd.model_dump()
                    )
                    session.add(job_entry)

                app_entry = session.query(ApplicationModel).filter_by(application_id=app.application_id).first()
                if not app_entry:
                    app_entry = ApplicationModel(
                        application_id=app.application_id,
                        company=app.company,
                        job_title=app.job_title,
                        job_url=app.job_url,
                        application_url=app.application_url,
                        match_score=app.match_score,
                        status=app.status.value,
                        application_method=app.application_method,
                        submission_details=app.submission_details,
                        resume_used=app.resume_used,
                        notes=app.notes,
                        score_breakdown=score.model_dump()
                    )
                    session.add(app_entry)
                else:
                    app_entry.match_score = app.match_score
                    app_entry.status = app.status.value
                    app_entry.application_method = app.application_method
                    app_entry.submission_details = app.submission_details
                    app_entry.resume_used = app.resume_used
                    app_entry.notes = app.notes
                    app_entry.score_breakdown = score.model_dump()

                session.commit()
        except Exception as e:
            logger.error(f"Failed to persist application to database: {e}")

    def _update_app_db(self, app: ApplicationRecord) -> None:
        try:
            with SessionLocal() as session:
                app_entry = session.query(ApplicationModel).filter_by(application_id=app.application_id).first()
                if app_entry:
                    app_entry.status = app.status.value
                    app_entry.application_method = app.application_method
                    app_entry.submission_details = app.submission_details
                    app_entry.applied_at = app.applied_at
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update application in DB: {e}")


application_service = ApplicationService()
