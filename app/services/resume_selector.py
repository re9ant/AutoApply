import json
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.models.job import ExtractedJobDescription

logger = logging.getLogger(__name__)


class ResumeVariant(BaseModel):
    filename: str
    title: str
    domain: str = "General"
    primary_engine: Optional[str] = None
    focus_areas: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    priority_score: int = 5


class ResumeSelector:
    """Service to recommend the most optimal resume version based on JD requirements across tech domains."""

    def __init__(self, index_path: Optional[Path | str] = None):
        self.index_path = settings.resolve_path(
            (Path(index_path) if index_path else settings.RESUMES_DIR / "index.json")
        )
        self._variants: List[ResumeVariant] = []
        self._load_variants()

    def _load_variants(self):
        if not self.index_path.exists():
            logger.warning(f"Resume registry not found at {self.index_path}. Using fallback defaults.")
            self._variants = [
                ResumeVariant(
                    filename="unity_gameplay.pdf",
                    title="Default Unity Gameplay Resume",
                    domain="Game Development",
                    primary_engine="Unity",
                    focus_areas=["gameplay", "c#", "unity"],
                    target_roles=["Gameplay Programmer", "Unity Developer"],
                    priority_score=10
                )
            ]
            return

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._variants = [ResumeVariant.model_validate(item) for item in data]
            logger.info(f"Loaded {len(self._variants)} resume variants from registry.")
        except Exception as e:
            logger.error(f"Error loading resume variants: {e}")
            self._variants = []

    def get_all_variants(self) -> List[ResumeVariant]:
        self._load_variants()
        return self._variants

    def select_best_resume(self, jd: ExtractedJobDescription) -> str:
        """Select the highest scoring resume variant for the given JD across all tech domains."""
        if not self._variants:
            self._load_variants()
            if not self._variants:
                return "general_software_engineer.pdf"

        best_variant = self._variants[0]
        highest_score = -1.0

        jd_text = (
            f"{jd.title} {' '.join(jd.primary_engines)} {' '.join(jd.primary_languages)} "
            f"{' '.join(jd.game_systems)} {' '.join(jd.hard_requirements)} {' '.join(jd.tech_stack)}"
        ).lower()

        for variant in self._variants:
            score = float(variant.priority_score)

            # Match target roles
            for role in variant.target_roles:
                if role.lower() in jd.title.lower() or jd.title.lower() in role.lower():
                    score += 25.0

            # Match focus areas / keywords
            for area in variant.focus_areas:
                if area.lower() in jd_text:
                    score += 6.0

            # Engine match (if applicable)
            if variant.primary_engine and variant.primary_engine != "None":
                if any(variant.primary_engine.lower() in e.lower() for e in jd.primary_engines):
                    score += 15.0

            if score > highest_score:
                highest_score = score
                best_variant = variant

        logger.info(
            f"Selected resume '{best_variant.filename}' (score: {highest_score:.1f}) for role: '{jd.title}' [{best_variant.domain}]"
        )
        return best_variant.filename


resume_selector = ResumeSelector()
