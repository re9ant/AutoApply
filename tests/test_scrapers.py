import pytest
from app.scrapers.base import ScrapeFilter
from app.scrapers.greenhouse import GreenhouseScraper
from app.scrapers.lever import LeverScraper
from app.scrapers.ashby import AshbyScraper
from app.scrapers.discovery_service import JobDiscoveryService, DiscoveryRequest


@pytest.mark.asyncio
async def test_greenhouse_scraper_filter_logic():
    scraper = GreenhouseScraper()
    filters = ScrapeFilter(keywords=["Unity", "Gameplay"], remote_only=True)

    # Test internal filter helper
    assert scraper._matches_filters("Senior Unity Gameplay Programmer", "Remote work available", "Remote", filters) is True
    assert scraper._matches_filters("Frontend React Engineer", "Onsite NY", "New York", filters) is False


@pytest.mark.asyncio
async def test_lever_scraper_filter_logic():
    scraper = LeverScraper()
    filters = ScrapeFilter(keywords=["Backend", "Python"], remote_only=False)

    assert scraper._matches_filters("Backend Engineer", "Python FastAPI development", "Remote", filters) is True
    assert scraper._matches_filters("Art Director", "Character modeling", "London", filters) is False


@pytest.mark.asyncio
async def test_discovery_presets_available():
    service = JobDiscoveryService()
    presets = service.get_supported_presets()

    assert len(presets) >= 5
    assert any(p["target"] == "riotgames" for p in presets)
    assert any(p["target"] == "supercell" for p in presets)
    assert any(p["target"] == "roblox" for p in presets)
