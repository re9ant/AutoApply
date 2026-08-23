from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for the Autonomous Job Application Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base workspace directory
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)

    # OpenAI API configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="LLM model name for JD analysis")
    OPENAI_TEMPERATURE: float = Field(default=0.1, description="Low temperature for deterministic structured extraction")

    # File paths
    CANDIDATE_PROFILE_PATH: Path = Field(
        default=Path("candidate/profile.json"),
        description="Path to the candidate profile JSON file"
    )
    RESUMES_DIR: Path = Field(
        default=Path("resumes"),
        description="Directory containing resume variants and index.json"
    )
    EXCEL_TRACKER_PATH: Path = Field(
        default=Path("data/tracker.xlsx"),
        description="Path to the Excel application tracker workbook"
    )
    EXCEL_AUTO_BACKUP: bool = Field(
        default=True,
        description="Automatically create a backup copy before modifying the Excel workbook"
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///data/autoapply.db",
        description="SQLAlchemy connection URI"
    )

    # Match Scoring Thresholds
    MINIMUM_AUTO_APPLY_SCORE: int = Field(
        default=75,
        description="Minimum score (0-100) to mark job as READY / auto-apply candidate"
    )
    MINIMUM_REVIEW_SCORE: int = Field(
        default=60,
        description="Minimum score (0-100) to keep in review queue before rejecting"
    )

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve a relative path against the project BASE_DIR."""
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.BASE_DIR / p).resolve()


settings = Settings()
