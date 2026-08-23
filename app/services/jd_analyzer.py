import logging
import re
from typing import Optional

from app.ai.client import ai_client, AIClient
from app.ai.prompts import JD_EXTRACTION_SYSTEM_PROMPT
from app.ai.schemas import JDExtractionResponse
from app.models.job import ExtractedJobDescription, WorkplaceType, EmploymentType

logger = logging.getLogger(__name__)


class JDAnalyzer:
    """Service to parse raw job descriptions into structured Pydantic models."""

    def __init__(self, client: Optional[AIClient] = None):
        self.client = client or ai_client

    async def analyze_jd(self, raw_text: str, application_url: Optional[str] = None) -> ExtractedJobDescription:
        """Parse raw job description text into ExtractedJobDescription."""
        if not raw_text or not raw_text.strip():
            raise ValueError("Job description text cannot be empty.")

        if self.client.is_available:
            try:
                extraction = await self.client.extract_structured(
                    system_prompt=JD_EXTRACTION_SYSTEM_PROMPT,
                    user_content=raw_text,
                    response_model=JDExtractionResponse
                )
                return ExtractedJobDescription(
                    title=extraction.title,
                    company=extraction.company,
                    location=extraction.location,
                    workplace_type=extraction.workplace_type,
                    employment_type=extraction.employment_type,
                    salary_min=extraction.salary_min,
                    salary_max=extraction.salary_max,
                    salary_currency=extraction.salary_currency,
                    experience_years_min=extraction.experience_years_min,
                    experience_years_max=extraction.experience_years_max,
                    primary_engines=extraction.primary_engines,
                    secondary_engines=extraction.secondary_engines,
                    primary_languages=extraction.primary_languages,
                    secondary_languages=extraction.secondary_languages,
                    game_systems=extraction.game_systems,
                    platforms=extraction.platforms,
                    responsibilities=extraction.responsibilities,
                    hard_requirements=extraction.hard_requirements,
                    preferred_requirements=extraction.preferred_requirements,
                    tech_stack=extraction.tech_stack,
                    visa_sponsorship=extraction.visa_sponsorship,
                    application_url=application_url or extraction.application_url,
                    raw_source=raw_text
                )
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to rule-based parser: {e}")

        # Fallback offline rule-based parser
        return self._heuristic_parse(raw_text, application_url)

    def _heuristic_parse(self, raw_text: str, application_url: Optional[str] = None) -> ExtractedJobDescription:
        """Rule-based extractor for offline development, tests, and fallbacks."""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        title = lines[0] if lines else "Game Programmer"
        company = "Unknown Studio"

        # Heuristic title/company extraction
        if " - " in title:
            parts = title.split(" - ", 1)
            title, company = parts[0].strip(), parts[1].strip()
        elif " at " in title:
            parts = title.split(" at ", 1)
            title, company = parts[0].strip(), parts[1].strip()

        # Engine detection
        engines = []
        if re.search(r"\bunity\b", raw_text, re.I):
            engines.append("Unity")
        if re.search(r"\bunreal(?:\s*engine)?(?:\s*5|\s*4)?\b", raw_text, re.I):
            engines.append("Unreal Engine")
        if re.search(r"\bgodot\b", raw_text, re.I):
            engines.append("Godot")

        # Language detection
        languages = []
        if re.search(r"(?:(?<!\w)c#(?!\w)|csharp)", raw_text, re.I):
            languages.append("C#")
        if re.search(r"(?:(?<!\w)c\+\+(?!\w)|cpp)", raw_text, re.I):
            languages.append("C++")
        if re.search(r"\bpython\b", raw_text, re.I):
            languages.append("Python")
        if re.search(r"\bhlsl\b|\bglsl\b|\bshaderlab\b|\bshaders?\b", raw_text, re.I):
            languages.append("HLSL")

        # Workplace detection
        workplace = WorkplaceType.UNKNOWN
        if re.search(r"\bremote\b", raw_text, re.I):
            workplace = WorkplaceType.REMOTE
        elif re.search(r"\bhybrid\b", raw_text, re.I):
            workplace = WorkplaceType.HYBRID
        elif re.search(r"\bon-?site\b|\bin-?office\b", raw_text, re.I):
            workplace = WorkplaceType.ONSITE

        # Game systems detection
        systems = []
        if re.search(r"\bgameplay\b|\bcombat\b|\bplayer controller\b", raw_text, re.I):
            systems.append("Gameplay Mechanics")
        if re.search(r"\bai\b|\bnpc\b|\bbehavior tree\b|\bpathfinding\b", raw_text, re.I):
            systems.append("AI / NPC Systems")
        if re.search(r"\btools?\b|\beditor\b|\bui toolkit\b|\bugui\b", raw_text, re.I):
            systems.append("UI & Tools")
        if re.search(r"\bmultiplayer\b|\bnetcode\b|\bnetworking\b", raw_text, re.I):
            systems.append("Multiplayer & Networking")
        if re.search(r"\bphysics\b|\bcollision\b", raw_text, re.I):
            systems.append("Physics")

        # Experience years detection
        exp_match = re.search(r"(\d+)\+?\s*(?:-\s*(\d+))?\s*(?:years?|yrs?)\s*(?:of\s*)?experience", raw_text, re.I)
        exp_min = int(exp_match.group(1)) if exp_match else None
        exp_max = int(exp_match.group(2)) if (exp_match and exp_match.group(2)) else None

        return ExtractedJobDescription(
            title=title,
            company=company,
            location="Remote" if workplace == WorkplaceType.REMOTE else "Unknown",
            workplace_type=workplace,
            employment_type=EmploymentType.FULL_TIME,
            experience_years_min=exp_min,
            experience_years_max=exp_max,
            primary_engines=engines[:1],
            secondary_engines=engines[1:],
            primary_languages=languages[:2],
            secondary_languages=languages[2:],
            game_systems=systems,
            responsibilities=[line for line in lines if line.startswith("-") or line.startswith("•")][:5],
            hard_requirements=[f"Experience with {', '.join(languages)}" if languages else "Programming experience"],
            tech_stack=engines + languages,
            application_url=application_url,
            raw_source=raw_text
        )


jd_analyzer = JDAnalyzer()
