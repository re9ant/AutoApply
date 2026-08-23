from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class DiscoveredJob(BaseModel):
    """Normalized data representation of a discovered job posting before full JD extraction."""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: str = Field(default="Unknown", description="Location or Remote")
    url: str = Field(..., description="Job posting or application URL")
    source: str = Field(..., description="Platform / Scraper source name (e.g. Greenhouse, Lever)")
    description_text: Optional[str] = Field(None, description="Full or snippet JD text if scraped")
    ats_id: Optional[str] = Field(None, description="Platform specific job ID if available")


class ScrapeFilter(BaseModel):
    """Filters used during discovery."""
    keywords: List[str] = Field(
        default_factory=lambda: ["Unity", "Gameplay", "Game Programmer", "Backend", "Software Engineer", "C#", "Python"]
    )
    locations: List[str] = Field(default_factory=list)
    remote_only: bool = False
    max_jobs_per_source: int = 15


class BaseJobScraper(ABC):
    """Abstract base class for all job scrapers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    async def scrape(self, target: str, filters: ScrapeFilter) -> List[DiscoveredJob]:
        """Scrape jobs from the given target (e.g. company handle, URL, or feed)."""
        pass
