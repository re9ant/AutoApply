import html
import logging
import re
from typing import List
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)


class GreenhouseScraper(BaseJobScraper):
    """Scrapes jobs from Greenhouse job boards (e.g. boards.greenhouse.io/{company})."""

    @property
    def source_name(self) -> str:
        return "Greenhouse"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        # Target can be a company slug (e.g. 'riotgames') or a full URL
        company_slug = target.strip().rstrip("/").split("/")[-1].lower()
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"

        discovered: List[DiscoveredJob] = []

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])

                    for item in jobs:
                        title = item.get("title", "")
                        location_obj = item.get("location", {})
                        location_name = location_obj.get("name", "Unknown") if isinstance(location_obj, dict) else str(location_obj)
                        job_url = item.get("absolute_url", f"https://boards.greenhouse.io/{company_slug}/jobs/{item.get('id')}")
                        raw_content = html.unescape(item.get("content", ""))
                        clean_text = re.sub(r"<[^>]+>", " ", raw_content).strip()

                        # Apply Keyword & Location Filtering
                        if self._matches_filters(title, clean_text, location_name, filters):
                            discovered.append(
                                DiscoveredJob(
                                    title=title,
                                    company=company_slug.replace("-", " ").title(),
                                    location=location_name,
                                    url=job_url,
                                    source=f"Greenhouse ({company_slug})",
                                    description_text=clean_text if clean_text else f"{title} at {company_slug}",
                                    ats_id=str(item.get("id"))
                                )
                            )

                        if len(discovered) >= filters.max_jobs_per_source:
                            break
        except Exception as e:
            logger.warning(f"Greenhouse scraper failed for '{target}': {e}")

        return discovered

    def _matches_filters(self, title: str, text: str, location: str, filters: ScrapeFilter) -> bool:
        combined = f"{title} {text} {location}".lower()

        if filters.remote_only and "remote" not in combined:
            return False

        if not filters.keywords:
            return True

        return any(kw.lower() in combined for kw in filters.keywords)
