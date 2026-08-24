"""Universal RSS 2.0 and Atom feed scraper for job discovery."""
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Optional
import httpx

from app.scrapers.base import BaseJobScraper, DiscoveredJob, ScrapeFilter

logger = logging.getLogger(__name__)

# XML namespaces used by Atom feeds
ATOM_NS = "http://www.w3.org/2005/Atom"


class RSSFeedScraper(BaseJobScraper):
    """Parses RSS 2.0 and Atom feeds to discover job listings."""

    @property
    def source_name(self) -> str:
        return "RSS Feed"

    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        """Fetch and parse an RSS or Atom feed URL, returning normalized DiscoveredJob objects."""
        if not target:
            return []
        discovered: List[DiscoveredJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "AutoApplyBot/1.0 (job-search-agent)"}
            ) as client:
                resp = await client.get(target)
                if resp.status_code != 200:
                    logger.warning(f"RSS feed returned {resp.status_code} for {target}")
                    return []
                try:
                    root = ET.fromstring(resp.content)
                except ET.ParseError as e:
                    logger.warning(f"XML parse error for {target}: {e}")
                    return []

                # Detect feed type: RSS 2.0 or Atom
                tag = root.tag.lower()
                if "feed" in tag:  # Atom feed
                    discovered = self._parse_atom(root, filters, target)
                else:  # RSS 2.0
                    discovered = self._parse_rss(root, filters, target)

        except httpx.TimeoutException:
            logger.warning(f"RSS feed timed out: {target}")
        except httpx.TooManyRedirects:
            logger.warning(f"Too many redirects for RSS feed: {target}")
        except Exception as e:
            logger.warning(f"RSS feed scraper failed for '{target}': {e}")

        return discovered

    def _parse_rss(self, root: ET.Element, filters: ScrapeFilter, feed_url: str) -> List[DiscoveredJob]:
        """Parse RSS 2.0 feed items."""
        jobs: List[DiscoveredJob] = []
        items = root.findall(".//item")
        source_name = self._guess_source_name(feed_url)

        for item in items:
            if len(jobs) >= filters.max_jobs_per_source:
                break

            title_raw = self._get_text(item, "title") or ""
            link = self._get_text(item, "link") or self._get_text(item, "guid") or ""
            desc_html = self._get_text(item, "description") or ""
            desc_text = self._strip_html(desc_html)

            title, company = self._extract_title_company(title_raw)
            if not title or not link:
                continue

            if self._matches_filters(title, desc_text, filters):
                jobs.append(DiscoveredJob(
                    title=title,
                    company=company,
                    location=self._extract_location(desc_text) or "Remote",
                    url=link,
                    source=source_name,
                    description_text=desc_text[:3000] if desc_text else f"{title} at {company}"
                ))
        return jobs

    def _parse_atom(self, root: ET.Element, filters: ScrapeFilter, feed_url: str) -> List[DiscoveredJob]:
        """Parse Atom feed entries."""
        jobs: List[DiscoveredJob] = []
        ns = {"atom": ATOM_NS}
        entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
        source_name = self._guess_source_name(feed_url)

        for entry in entries:
            if len(jobs) >= filters.max_jobs_per_source:
                break

            def t(tag: str) -> Optional[str]:
                el = entry.find(f"{{{ATOM_NS}}}{tag}") or entry.find(tag)
                return el.text.strip() if el is not None and el.text else None

            title_raw = t("title") or ""
            link_el = entry.find(f"{{{ATOM_NS}}}link") or entry.find("link")
            link = ""
            if link_el is not None:
                link = link_el.get("href") or link_el.text or ""
            if not link:
                id_el = entry.find(f"{{{ATOM_NS}}}id") or entry.find("id")
                link = id_el.text if id_el is not None else ""

            summary_el = (
                entry.find(f"{{{ATOM_NS}}}summary") or
                entry.find("summary") or
                entry.find(f"{{{ATOM_NS}}}content") or
                entry.find("content")
            )
            desc_text = self._strip_html(summary_el.text or "") if summary_el is not None else ""

            title, company = self._extract_title_company(title_raw)
            if not title or not link:
                continue

            if self._matches_filters(title, desc_text, filters):
                jobs.append(DiscoveredJob(
                    title=title,
                    company=company,
                    location=self._extract_location(desc_text) or "Remote",
                    url=link.strip(),
                    source=source_name,
                    description_text=desc_text[:3000] if desc_text else f"{title} at {company}"
                ))
        return jobs

    def _extract_title_company(self, raw: str) -> tuple:
        """Extract job title and company from common RSS title formats."""
        raw = raw.strip()
        # "Role at Company" pattern
        if " at " in raw:
            parts = raw.split(" at ", 1)
            return parts[0].strip(), parts[1].strip()
        # "Company - Role" or "Company — Role" pattern
        for sep in [" — ", " – ", " | "]:
            if sep in raw:
                parts = raw.split(sep, 1)
                return parts[1].strip(), parts[0].strip()
        if " - " in raw:
            parts = raw.split(" - ", 1)
            # Heuristic: shorter part is usually company
            if len(parts[0]) < len(parts[1]):
                return parts[1].strip(), parts[0].strip()
            return parts[0].strip(), parts[1].strip()
        return raw, "Unknown Studio"

    def _matches_filters(self, title: str, text: str, filters: ScrapeFilter) -> bool:
        if not filters.keywords:
            return True
        combined = f"{title} {text}".lower()
        return any(kw.lower() in combined for kw in filters.keywords)

    def _extract_location(self, text: str) -> Optional[str]:
        loc_match = re.search(
            r"(?:location|based in|located in|\bloc\b)[:\s]+([\w ,]+?)(?:\.|,|\n|$)",
            text, re.IGNORECASE
        )
        if loc_match:
            candidate = loc_match.group(1).strip()[:50]
            if candidate:
                return candidate
        if re.search(r"\bremote\b", text, re.IGNORECASE):
            return "Remote"
        return None

    def _strip_html(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _get_text(self, el: ET.Element, tag: str) -> Optional[str]:
        child = el.find(tag)
        if child is not None:
            return (child.text or "").strip() or None
        return None

    def _guess_source_name(self, url: str) -> str:
        """Derive a human-readable source name from a feed URL."""
        name_map = {
            "remotegamejobs": "RemoteGameJobs",
            "weworkremotely": "WeWorkRemotely",
            "remotive": "Remotive",
            "jobicy": "Jobicy",
            "remoteok": "RemoteOK",
            "hitmarker": "Hitmarker",
            "gamesindustry": "GamesIndustry.biz",
        }
        url_lower = url.lower()
        for key, display in name_map.items():
            if key in url_lower:
                return display
        try:
            domain = url.split("//")[-1].split("/")[0].replace("www.", "")
            return domain.split(".")[0].capitalize()
        except Exception:
            return "RSS Feed"


rss_scraper = RSSFeedScraper()
