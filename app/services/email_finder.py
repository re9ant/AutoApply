"""Company website deep-scraper to find HR/recruiter email addresses."""
import logging
import re
from typing import Optional, List
import httpx

logger = logging.getLogger(__name__)

# Email regex — conservative, avoids false positives
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]{2,}@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}"
)

# Recruiter/HR keyword signals (ordered by priority)
HR_KEYWORDS = ["hr", "careers", "career", "jobs", "recruit", "talent", "hiring", "apply", "people", "team"]

# Pages to probe on the company's website
CAREERS_PATHS = ["/careers", "/jobs", "/contact", "/about", "/team", "/hiring", "/work-with-us", "/join-us", ""]

# Domains to skip (known ATS platforms, CDNs, asset servers)
SKIP_DOMAINS = {
    "example.com", "wix.com", "schema.org", "sentry.io", "cloudflare.com",
    "github.com", "linkedin.com", "twitter.com", "facebook.com",
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
    "jobvite.com", "smartrecruiters.com"
}


class CompanyEmailFinder:
    """Find HR/recruiting emails by scraping RSS descriptions and company websites."""

    async def find_email(
        self,
        job_url: Optional[str],
        company: str,
        description_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Try multiple strategies to find a recruiter/HR email:
        1. Scan RSS description text directly.
        2. Visit company website and common sub-paths.
        3. Return None if not found (caller shows manual input UI).
        """
        # Strategy 1: scan description text
        if description_text:
            email = self._extract_best_email(description_text)
            if email:
                logger.debug(f"Found email in description for '{company}': {email}")
                return email

        # Strategy 2: derive company root domain from job URL
        root_domain = self._extract_company_domain(job_url, company)
        if not root_domain:
            return None

        # Skip if domain is an ATS platform
        base = root_domain.lower()
        if any(skip in base for skip in SKIP_DOMAINS):
            logger.debug(f"Skipping ATS/CDN domain for email search: {root_domain}")
            return None

        # Strategy 3: probe company website paths
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AutoApplyBot/1.0)"}
            ) as client:
                for path in CAREERS_PATHS:
                    url = f"https://{root_domain}{path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            email = self._extract_best_email(resp.text)
                            if email:
                                logger.info(f"Found HR email for '{company}' at {url}: {email}")
                                return email
                    except Exception as e:
                        logger.debug(f"Failed to fetch {url}: {e}")
                        continue
        except Exception as e:
            logger.debug(f"Email finder outer error for '{company}': {e}")

        return None

    def _extract_best_email(self, text: str) -> Optional[str]:
        """Find the best HR/recruiter email from a block of text."""
        matches = EMAIL_REGEX.findall(text or "")
        hr_emails = []
        generic_emails = []

        for match in matches:
            m_lower = match.lower()
            domain = m_lower.split("@")[-1]

            # Skip known non-HR domains
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue
            # Skip obviously fake or placeholder emails
            if any(bad in m_lower for bad in ["noreply", "no-reply", "donotreply", "example", "test@", "info@info"]):
                continue

            if any(kw in m_lower for kw in HR_KEYWORDS):
                hr_emails.append(match)
            else:
                generic_emails.append(match)

        # Prefer specific HR-keyword emails, fall back to first generic company email
        if hr_emails:
            return hr_emails[0]
        if generic_emails:
            return generic_emails[0]
        return None

    def _extract_company_domain(self, job_url: Optional[str], company: str) -> Optional[str]:
        """Derive the company's root domain from the job posting URL."""
        if job_url:
            # Strip protocol and path
            domain = job_url.split("//")[-1].split("/")[0].lower()
            domain = domain.lstrip("www.")
            # Skip ATS-hosted pages (greenhouse, lever, ashby)
            ats_hosts = ["greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "jobvite.com"]
            if not any(ats in domain for ats in ats_hosts):
                if "." in domain and len(domain) > 4:
                    return domain

        # Fallback: construct guessed domain from company name
        safe = re.sub(r"[^a-zA-Z0-9]", "", company).lower()
        if not safe:
            return None
        # Try to detect if it's a game company
        if "game" in company.lower() or "studio" in company.lower() or "interactive" in company.lower():
            return f"{safe}games.com"
        return f"{safe}.com"


email_finder = CompanyEmailFinder()
