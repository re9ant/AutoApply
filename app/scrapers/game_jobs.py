import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import List
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)


class GameJobsScraper(BaseJobScraper):
    """Scrapes game development jobs from public RSS and web feeds (e.g. RemoteGameJobs, Hitmarker public feed)."""

    @property
    def source_name(self) -> str:
        return "GameJobs Feed"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        feed_url = target or "https://remotegamejobs.com/feed"
        discovered: List[DiscoveredJob] = []

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(feed_url)
                if resp.status_code == 200:
                    # Attempt RSS XML parse
                    try:
                        root = ET.fromstring(resp.content)
                        # RSS 2.0 items
                        items = root.findall(".//item")
                        for item in items:
                            title_elem = item.find("title")
                            link_elem = item.find("link")
                            desc_elem = item.find("description")

                            title = title_elem.text if title_elem is not None else ""
                            link = link_elem.text if link_elem is not None else ""
                            desc_html = desc_elem.text if desc_elem is not None else ""
                            clean_text = re.sub(r"<[^>]+>", " ", html.unescape(desc_html)).strip()

                            # Extract company from title if format is "Role at Company"
                            company = "Game Studio"
                            if " at " in title:
                                parts = title.split(" at ", 1)
                                title, company = parts[0].strip(), parts[1].strip()
                            elif " - " in title:
                                parts = title.split(" - ", 1)
                                company, title = parts[0].strip(), parts[1].strip()

                            if self._matches_filters(title, clean_text, filters):
                                discovered.append(
                                    DiscoveredJob(
                                        title=title,
                                        company=company,
                                        location="Remote",
                                        url=link,
                                        source="RemoteGameJobs Feed",
                                        description_text=clean_text if clean_text else f"{title} at {company}"
                                    )
                                )

                            if len(discovered) >= filters.max_jobs_per_source:
                                break
                    except Exception as parse_err:
                        logger.debug(f"RSS parse error: {parse_err}")
        except Exception as e:
            logger.warning(f"GameJobs feed scraper failed for '{target}': {e}")

        return discovered

    def _matches_filters(self, title: str, text: str, filters: ScrapeFilter) -> bool:
        combined = f"{title} {text}".lower()

        if not filters.keywords:
            return True

        return any(kw.lower() in combined for kw in filters.keywords)
