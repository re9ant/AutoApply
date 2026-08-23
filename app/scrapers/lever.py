import logging
import re
from typing import List
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)


class LeverScraper(BaseJobScraper):
    """Scrapes jobs from Lever job boards (e.g. jobs.lever.co/{company})."""

    @property
    def source_name(self) -> str:
        return "Lever"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        company_slug = target.strip().rstrip("/").split("/")[-1].lower()
        api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"

        discovered: List[DiscoveredJob] = []

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    jobs = resp.json()

                    for item in jobs:
                        title = item.get("text", "")
                        categories = item.get("categories", {})
                        location_name = categories.get("location", "Unknown") if isinstance(categories, dict) else "Unknown"
                        job_url = item.get("hostedUrl", f"https://jobs.lever.co/{company_slug}/{item.get('id')}")
                        desc_plain = item.get("descriptionPlain", "") or ""
                        additional_plain = item.get("additionalPlain", "") or ""
                        clean_text = f"{desc_plain}\n{additional_plain}".strip()

                        if self._matches_filters(title, clean_text, location_name, filters):
                            discovered.append(
                                DiscoveredJob(
                                    title=title,
                                    company=company_slug.replace("-", " ").title(),
                                    location=location_name,
                                    url=job_url,
                                    source=f"Lever ({company_slug})",
                                    description_text=clean_text if clean_text else f"{title} at {company_slug}",
                                    ats_id=str(item.get("id"))
                                )
                            )

                        if len(discovered) >= filters.max_jobs_per_source:
                            break
        except Exception as e:
            logger.warning(f"Lever scraper failed for '{target}': {e}")

        return discovered

    def _matches_filters(self, title: str, text: str, location: str, filters: ScrapeFilter) -> bool:
        combined = f"{title} {text} {location}".lower()

        if filters.remote_only and "remote" not in combined:
            return False

        if not filters.keywords:
            return True

        return any(kw.lower() in combined for kw in filters.keywords)
