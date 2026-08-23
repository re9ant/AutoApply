import logging
from typing import Optional, Tuple
from app.database.models import ApplicationModel, JobModel
from app.database.session import SessionLocal, init_db
from app.models.application import ApplicationRecord, ApplicationStatus
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, MatchScoreBreakdown
from app.services.excel_tracker import excel_tracker, ExcelTracker
from app.services.jd_analyzer import jd_analyzer, JDAnalyzer
from app.services.job_scorer import job_scorer, JobScorer
from app.services.profile_loader import profile_loader, ProfileLoader
from app.services.resume_selector import resume_selector, ResumeSelector

logger = logging.getLogger(__name__)


class ApplicationService:
    """Core orchestrator coordinating JD analysis, candidate matching, resume selection, and Excel sync."""

    def __init__(
        self,
        loader: Optional[ProfileLoader] = None,
        analyzer: Optional[JDAnalyzer] = None,
        scorer: Optional[JobScorer] = None,
        selector: Optional[ResumeSelector] = None,
        tracker: Optional[ExcelTracker] = None,
    ):
        self.loader = loader or profile_loader
        self.analyzer = analyzer or jd_analyzer
        self.scorer = scorer or job_scorer
        self.selector = selector or resume_selector
        self.tracker = tracker or excel_tracker
        init_db()

    async def process_job_posting(
        self,
        raw_jd_text: str,
        job_url: Optional[str] = None,
        application_url: Optional[str] = None,
        source: str = "Direct / Manual"
    ) -> Tuple[ApplicationRecord, MatchScoreBreakdown]:
        """Complete workflow for discovering, analyzing, scoring, and recording a game dev job posting."""
        # 1. Load verified candidate profile
        profile: CandidateProfile = self.loader.load_profile()

        # 2. Extract structured JD
        extracted_jd: ExtractedJobDescription = await self.analyzer.analyze_jd(
            raw_text=raw_jd_text,
            application_url=application_url or job_url
        )

        # 3. Compute hybrid match score
        score_breakdown: MatchScoreBreakdown = self.scorer.calculate_match(
            jd=extracted_jd,
            profile=profile
        )

        # 4. Select the optimal resume variant
        recommended_resume = self.selector.select_best_resume(extracted_jd)
        score_breakdown.recommended_resume_filename = recommended_resume

        # 5. Determine initial application status
        if score_breakdown.recommended_action == "AUTO_APPLY":
            status = ApplicationStatus.READY
        elif score_breakdown.recommended_action == "REVIEW_QUEUE":
            status = ApplicationStatus.WAITING_FOR_USER
        elif score_breakdown.recommended_action == "REJECT":
            status = ApplicationStatus.REJECTED
        else:
            status = ApplicationStatus.ANALYZED

        # 6. Create application record
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
            notes=score_breakdown.match_summary,
            structured_jd=extracted_jd.model_dump(),
            scoring_breakdown=score_breakdown.model_dump()
        )

        # 7. Persist to internal database
        self._save_to_database(app_record, extracted_jd, score_breakdown)

        # 8. Synchronize to Excel workbook
        excel_action, row_num = self.tracker.upsert_application(app_record)
        logger.info(f"Synchronized with Excel (action: {excel_action}, row: {row_num})")

        return app_record, score_breakdown

    def _save_to_database(
        self,
        app: ApplicationRecord,
        jd: ExtractedJobDescription,
        score: MatchScoreBreakdown
    ) -> None:
        """Record application to local SQLite/Postgres DB."""
        try:
            with SessionLocal() as session:
                # Upsert or insert job
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

                # Upsert application
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
                        resume_used=app.resume_used,
                        notes=app.notes,
                        score_breakdown=score.model_dump()
                    )
                    session.add(app_entry)
                else:
                    app_entry.match_score = app.match_score
                    app_entry.status = app.status.value
                    app_entry.resume_used = app.resume_used
                    app_entry.notes = app.notes
                    app_entry.score_breakdown = score.model_dump()

                session.commit()
        except Exception as e:
            logger.error(f"Failed to persist application to database: {e}")


application_service = ApplicationService()
