import logging
import re
from typing import List
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)


class AshbyScraper(BaseJobScraper):
    """Scrapes jobs from Ashby job boards (e.g. jobs.ashbyhq.com/{company})."""

    @property
    def source_name(self) -> str:
        return "Ashby"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        company_slug = target.strip().rstrip("/").split("/")[-1].lower()
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"

        discovered: List[DiscoveredJob] = []

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])

                    for item in jobs:
                        title = item.get("title", "")
                        location_name = item.get("location", "Unknown")
                        job_url = item.get("jobUrl", f"https://jobs.ashbyhq.com/{company_slug}/{item.get('id')}")
                        desc_html = item.get("descriptionHtml", "") or ""
                        clean_text = re.sub(r"<[^>]+>", " ", desc_html).strip()

                        if self._matches_filters(title, clean_text, location_name, filters):
                            discovered.append(
                                DiscoveredJob(
                                    title=title,
                                    company=company_slug.replace("-", " ").title(),
                                    location=location_name,
                                    url=job_url,
                                    source=f"Ashby ({company_slug})",
                                    description_text=clean_text if clean_text else f"{title} at {company_slug}",
                                    ats_id=str(item.get("id"))
                                )
                            )

                        if len(discovered) >= filters.max_jobs_per_source:
                            break
        except Exception as e:
            logger.warning(f"Ashby scraper failed for '{target}': {e}")

        return discovered

    def _matches_filters(self, title: str, text: str, location: str, filters: ScrapeFilter) -> bool:
        combined = f"{title} {text} {location}".lower()

        if filters.remote_only and "remote" not in combined:
            return False

        if not filters.keywords:
            return True

        return any(kw.lower() in combined for kw in filters.keywords)
