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
from app.scrapers.web_page import WebPageScraper
from app.services.application_service import application_service, ApplicationService
from app.services.excel_tracker import excel_tracker, ExcelTracker

logger = logging.getLogger(__name__)


# Preset top game studios and tech companies with public ATS boards
POPULAR_STUDIO_PRESETS = [
    {"name": "Phoenix Labs", "type": "greenhouse", "target": "phoenixlabs", "category": "Game Dev"},
    {"name": "Riot Games", "type": "greenhouse", "target": "riotgames", "category": "Game Dev"},
    {"name": "Supercell", "type": "greenhouse", "target": "supercell", "category": "Game Dev"},
    {"name": "Respawn / EA", "type": "greenhouse", "target": "respawn", "category": "Game Dev"},
    {"name": "Innersloth", "type": "ashby", "target": "innersloth", "category": "Game Dev"},
    {"name": "Roblox", "type": "lever", "target": "roblox", "category": "Game & Tech"},
    {"name": "Scale AI", "type": "ashby", "target": "scaleai", "category": "AI / Tech"},
    {"name": "RemoteGameJobs Feed", "type": "feed", "target": "https://remotegamejobs.com/feed", "category": "Game Dev"},
]


class DiscoveryRequest(BaseModel):
    selected_presets: List[str] = Field(default_factory=lambda: ["phoenixlabs", "riotgames", "supercell", "roblox"])
    custom_targets: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of custom dicts: [{'type': 'greenhouse'|'lever'|'ashby'|'web', 'target': 'url_or_handle'}]"
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


class DiscoveryResponse(BaseModel):
    total_discovered: int
    new_jobs_processed: int
    duplicates_skipped: int
    results: List[DiscoveredJobResult]


class JobDiscoveryService:
    """Orchestrates multi-source scraping, deduplication, batch JD analysis, scoring, and Excel sync."""

    def __init__(self, app_service: Optional[ApplicationService] = None, tracker: Optional[ExcelTracker] = None):
        self.app_service = app_service or application_service
        self.tracker = tracker or excel_tracker
        self.scrapers: Dict[str, BaseJobScraper] = {
            "greenhouse": GreenhouseScraper(),
            "lever": LeverScraper(),
            "ashby": AshbyScraper(),
            "feed": GameJobsScraper(),
            "web": WebPageScraper(),
        }

    def get_supported_presets(self) -> List[Dict[str, Any]]:
        return POPULAR_STUDIO_PRESETS

    async def run_discovery(self, request: DiscoveryRequest) -> DiscoveryResponse:
        """Run scraping across selected sources, match each job, and sync to Excel."""
        filters = ScrapeFilter(
            keywords=request.keywords,
            locations=request.locations,
            remote_only=request.remote_only,
            max_jobs_per_source=request.max_jobs_per_source
        )

        tasks = []

        # 1. Add preset targets
        for preset in POPULAR_STUDIO_PRESETS:
            if preset["target"] in request.selected_presets:
                scraper = self.scrapers.get(preset["type"])
                if scraper:
                    tasks.append(scraper.scrape(preset["target"], filters))

        # 2. Add custom targets
        for custom in request.custom_targets:
            target_type = custom.get("type", "web").lower()
            target_val = custom.get("target", "").strip()
            if target_val:
                scraper = self.scrapers.get(target_type) or self.scrapers["web"]
                tasks.append(scraper.scrape(target_val, filters))

        if not tasks:
            # Fallback default scrape
            tasks.append(self.scrapers["greenhouse"].scrape("phoenixlabs", filters))

        # Run scrapers concurrently
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

        for disc in all_discovered:
            clean_url = disc.url.strip().lower()
            combo = f"{disc.company.strip().lower()}-{disc.title.strip().lower()}"

            is_duplicate = (clean_url in existing_urls) or (combo in existing_combos)

            if is_duplicate:
                duplicates_count += 1
                results.append(
                    DiscoveredJobResult(
                        discovered_job=disc,
                        already_tracked=True,
                        decision_status="ALREADY_TRACKED"
                    )
                )
                continue

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
                    results.append(
                        DiscoveredJobResult(
                            discovered_job=disc,
                            match_score=score_breakdown.total_score,
                            decision_status=app_record.status.value,
                            recommended_resume=score_breakdown.recommended_resume_filename,
                            already_tracked=False
                        )
                    )
                except Exception as e:
                    logger.error(f"Error processing discovered job '{disc.title}': {e}")
                    results.append(
                        DiscoveredJobResult(
                            discovered_job=disc,
                            already_tracked=False,
                            decision_status="ANALYSIS_ERROR"
                        )
                    )
            else:
                results.append(
                    DiscoveredJobResult(
                        discovered_job=disc,
                        already_tracked=False,
                        decision_status="DISCOVERED"
                    )
                )

        return DiscoveryResponse(
            total_discovered=len(all_discovered),
            new_jobs_processed=new_processed_count,
            duplicates_skipped=duplicates_count,
            results=results
        )


discovery_service = JobDiscoveryService()
