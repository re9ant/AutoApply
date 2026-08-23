import logging
import re
from typing import List
from urllib.parse import urljoin
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)


class WebPageScraper(BaseJobScraper):
    """Scrapes job links and text from generic company career web pages."""

    @property
    def source_name(self) -> str:
        return "Web Career Page"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"

        discovered: List[DiscoveredJob] = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(target)
                if resp.status_code == 200:
                    html_content = resp.text

                    # Regex link extractor looking for job/career patterns
                    link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.DOTALL)
                    matches = link_pattern.findall(html_content)

                    for href, raw_text in matches:
                        title_clean = re.sub(r"<[^>]+>", " ", raw_text).strip()
                        full_url = urljoin(target, href)

                        # Filter out navigation links, privacy policy, etc.
                        if len(title_clean) < 4 or any(skip in title_clean.lower() for skip in ["home", "privacy", "terms", "cookie", "login", "contact", "about"]):
                            continue

                        # Check if link looks like a job link or title matches keywords
                        is_job_link = any(pattern in href.lower() for pattern in ["/job", "/career", "/position", "/opening", "greenhouse.io", "lever.co", "ashbyhq.com"])
                        has_keyword = any(kw.lower() in title_clean.lower() for kw in filters.keywords) if filters.keywords else True

                        if (is_job_link or has_keyword) and len(title_clean) > 5:
                            # Avoid duplicates
                            if not any(d.url == full_url for d in discovered):
                                discovered.append(
                                    DiscoveredJob(
                                        title=title_clean,
                                        company=self._extract_domain_name(target),
                                        location="Unknown",
                                        url=full_url,
                                        source=f"Web Page ({target})",
                                        description_text=f"{title_clean} at {target}"
                                    )
                                )

                        if len(discovered) >= filters.max_jobs_per_source:
                            break
        except Exception as e:
            logger.warning(f"WebPage scraper failed for '{target}': {e}")

        return discovered

    def _extract_domain_name(self, url: str) -> str:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "").split(".")[0]
        return domain.capitalize()
