import asyncio
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.application import ApplicationRecord, ApplicationStatus
from app.models.job import MatchScoreBreakdown
from app.scrapers.ashby import AshbyScraper
from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter
from app.scrapers.game_jobs import GameJobsScraper
from app.scrapers.greenhouse import GreenhouseScraper
from app.scrapers.lever import LeverScraper
from app.scrapers.rss_scraper import RSSFeedScraper
from app.scrapers.web_page import WebPageScraper
from app.services.application_service import application_service, ApplicationService
from app.services.email_finder import email_finder
from app.services.excel_tracker import excel_tracker, ExcelTracker

logger = logging.getLogger(__name__)


# RSS feed presets — these are the primary discovery sources
RSS_FEED_PRESETS = [
    {"name": "Remote Game Jobs",     "type": "rss", "target": "https://remotegamejobs.com/feed",                                      "category": "Game Dev"},
    {"name": "WeWorkRemotely Games",  "type": "rss", "target": "https://weworkremotely.com/categories/remote-game-dev-jobs.rss",      "category": "Game Dev"},
    {"name": "WeWorkRemotely Prog",   "type": "rss", "target": "https://weworkremotely.com/categories/remote-programming-jobs.rss",   "category": "Programming"},
    {"name": "Remotive (Dev)",        "type": "rss", "target": "https://remotive.com/remote-jobs/feed/software-dev",                  "category": "Tech"},
    {"name": "Jobicy (Remote)",       "type": "rss", "target": "https://jobicy.com/?feed=job_feed",                                   "category": "Tech"},
    {"name": "RemoteOK",              "type": "rss", "target": "https://remoteok.com/remote-jobs.rss",                               "category": "Tech"},
    {"name": "Hitmarker Game Jobs",   "type": "rss", "target": "https://hitmarker.net/rss",                                          "category": "Game Dev"},
]

# Keep ATS presets available (not default-selected but still usable)
POPULAR_STUDIO_PRESETS = RSS_FEED_PRESETS


class DiscoveryRequest(BaseModel):
    selected_presets: List[str] = Field(
        default_factory=lambda: [
            "https://remotegamejobs.com/feed",
            "https://weworkremotely.com/categories/remote-game-dev-jobs.rss",
        ]
    )
    custom_targets: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of custom dicts: [{'type': 'rss', 'target': 'https://example.com/feed.rss'}]"
    )
    rss_urls: List[str] = Field(
        default_factory=list,
        description="Additional custom RSS feed URLs to scrape"
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["Unity", "Gameplay", "Game Programmer", "Backend", "Software Engineer", "C#", "Python"]
    )
    locations: List[str] = Field(default_factory=list)
    remote_only: bool = False
    auto_score_and_sync: bool = True
    max_jobs_per_source: int = 10


class DiscoveredJobResult(BaseModel):
    discovered_job: DiscoveredJob
    match_score: Optional[float] = None
    decision_status: Optional[str] = None
    recommended_resume: Optional[str] = None
    already_tracked: bool = False
    hr_email: Optional[str] = None
    email_status: str = "PENDING"  # FOUND | NOT_FOUND | PENDING


class DiscoveryResponse(BaseModel):
    total_discovered: int
    new_jobs_processed: int
    duplicates_skipped: int
    results: List[DiscoveredJobResult]


class JobDiscoveryService:
    """Orchestrates RSS feed scraping, deduplication, batch JD analysis, scoring, email finding, and Excel sync."""

    def __init__(self, app_service: Optional[ApplicationService] = None, tracker: Optional[ExcelTracker] = None):
        self.app_service = app_service or application_service
        self.tracker = tracker or excel_tracker
        self.rss_scraper = RSSFeedScraper()
        # Keep ATS scrapers available for custom_targets if user specifies them
        self.scrapers: Dict[str, BaseJobScraper] = {
            "rss": self.rss_scraper,
            "feed": self.rss_scraper,  # backward compat alias
            "greenhouse": GreenhouseScraper(),
            "lever": LeverScraper(),
            "ashby": AshbyScraper(),
            "web": WebPageScraper(),
        }

    def get_supported_presets(self) -> List[Dict[str, Any]]:
        return RSS_FEED_PRESETS

    async def run_discovery(self, request: DiscoveryRequest) -> DiscoveryResponse:
        """Run RSS feed scraping, match each job, find HR emails, and sync to Excel."""
        filters = ScrapeFilter(
            keywords=request.keywords,
            locations=request.locations,
            remote_only=request.remote_only,
            max_jobs_per_source=request.max_jobs_per_source
        )

        tasks = []

        # 1. Add selected RSS preset feeds
        for preset in RSS_FEED_PRESETS:
            if preset["target"] in request.selected_presets:
                tasks.append(self.rss_scraper.scrape(preset["target"], filters))

        # 2. Add custom RSS URL targets
        for rss_url in request.rss_urls:
            if rss_url.strip():
                tasks.append(self.rss_scraper.scrape(rss_url.strip(), filters))

        # 3. Add custom_targets (backward compat — supports rss, greenhouse, lever, etc.)
        for custom in request.custom_targets:
            target_type = custom.get("type", "rss").lower()
            target_val = custom.get("target", "").strip()
            if target_val:
                scraper = self.scrapers.get(target_type) or self.rss_scraper
                tasks.append(scraper.scrape(target_val, filters))

        if not tasks:
            # Default: scrape RemoteGameJobs if nothing selected
            tasks.append(self.rss_scraper.scrape("https://remotegamejobs.com/feed", filters))

        # Run all feed scrapers concurrently
        scrape_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_discovered: List[DiscoveredJob] = []
        for res in scrape_results:
            if isinstance(res, list):
                all_discovered.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Scraper error during discovery: {res}")

        # Get currently tracked applications for deduplication
        existing_apps = self.tracker.get_all_applications()
        existing_urls = {
            str(app.get("job_url", "")).strip().lower()
            for app in existing_apps
            if app.get("job_url")
        }
        existing_combos = {
            f"{str(app.get('company', '')).strip().lower()}-{str(app.get('job_title', '')).strip().lower()}"
            for app in existing_apps
        }

        results: List[DiscoveredJobResult] = []
        new_processed_count = 0
        duplicates_count = 0

        # Find HR emails concurrently for all new non-duplicate jobs
        email_tasks = []
        non_dup_jobs = []

        for disc in all_discovered:
            clean_url = disc.url.strip().lower()
            combo = f"{disc.company.strip().lower()}-{disc.title.strip().lower()}"
            is_duplicate = (clean_url in existing_urls) or (combo in existing_combos)

            if is_duplicate:
                duplicates_count += 1
                results.append(DiscoveredJobResult(
                    discovered_job=disc,
                    already_tracked=True,
                    decision_status="ALREADY_TRACKED"
                ))
            else:
                non_dup_jobs.append(disc)
                email_tasks.append(
                    email_finder.find_email(
                        job_url=disc.url,
                        company=disc.company,
                        description_text=disc.description_text
                    )
                )

        # Run email finding concurrently
        email_results = await asyncio.gather(*email_tasks, return_exceptions=True)

        for disc, email_result in zip(non_dup_jobs, email_results):
            hr_email = email_result if isinstance(email_result, str) else None
            email_status = "FOUND" if hr_email else "NOT_FOUND"

            # Process new job posting if auto_score_and_sync is enabled
            if request.auto_score_and_sync:
                try:
                    jd_text = disc.description_text or f"{disc.title} at {disc.company}. Location: {disc.location}"
                    app_record, score_breakdown = await self.app_service.process_job_posting(
                        raw_jd_text=jd_text,
                        job_url=disc.url,
                        application_url=disc.url,
                        source=disc.source
                    )
                    new_processed_count += 1
                    results.append(DiscoveredJobResult(
                        discovered_job=disc,
                        match_score=score_breakdown.total_score,
                        decision_status=app_record.status.value,
                        recommended_resume=score_breakdown.recommended_resume_filename,
                        already_tracked=False,
                        hr_email=hr_email,
                        email_status=email_status
                    ))
                except Exception as e:
                    logger.error(f"Error processing discovered job '{disc.title}': {e}")
                    results.append(DiscoveredJobResult(
                        discovered_job=disc,
                        already_tracked=False,
                        decision_status="ANALYSIS_ERROR",
                        hr_email=hr_email,
                        email_status=email_status
                    ))
            else:
                results.append(DiscoveredJobResult(
                    discovered_job=disc,
                    already_tracked=False,
                    decision_status="DISCOVERED",
                    hr_email=hr_email,
                    email_status=email_status
                ))

        return DiscoveryResponse(
            total_discovered=len(all_discovered),
            new_jobs_processed=new_processed_count,
            duplicates_skipped=duplicates_count,
            results=results
        )


discovery_service = JobDiscoveryService()
