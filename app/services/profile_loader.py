import json
import logging
from pathlib import Path
from typing import Optional

from app.config.settings import settings
from app.models.candidate import CandidateProfile

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Service to load, validate, and cache the candidate profile."""

    def __init__(self, profile_path: Optional[Path | str] = None):
        self.profile_path = settings.resolve_path(profile_path or settings.CANDIDATE_PROFILE_PATH)
        self._cached_profile: Optional[CandidateProfile] = None

    def load_profile(self, force_reload: bool = False) -> CandidateProfile:
        """Load and strictly validate candidate profile from JSON file."""
        if self._cached_profile is not None and not force_reload:
            return self._cached_profile

        if not self.profile_path.exists():
            raise FileNotFoundError(
                f"Candidate profile not found at: {self.profile_path}. "
                f"Please create the file or copy candidate/profile_example.json."
            )

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            profile = CandidateProfile.model_validate(data)
            self._cached_profile = profile
            logger.info(f"Loaded valid candidate profile for: {profile.candidate.name}")
            return profile
        except Exception as e:
            logger.error(f"Failed to parse and validate candidate profile: {e}")
            raise


profile_loader = ProfileLoader()
