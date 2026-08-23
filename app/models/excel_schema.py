from typing import Dict, List
from pydantic import BaseModel, Field


class ExcelColumnDefinition(BaseModel):
    key: str
    canonical_header: str
    aliases: List[str] = Field(default_factory=list)
    width: int = 18


# Standard default columns & synonyms to recognize existing user workbooks
DEFAULT_EXCEL_COLUMNS: List[ExcelColumnDefinition] = [
    ExcelColumnDefinition(
        key="application_id",
        canonical_header="Application ID",
        aliases=["app_id", "id", "application id", "job id", "app id"],
        width=16
    ),
    ExcelColumnDefinition(
        key="company",
        canonical_header="Company",
        aliases=["company name", "studio", "employer", "organization"],
        width=20
    ),
    ExcelColumnDefinition(
        key="job_title",
        canonical_header="Job Title",
        aliases=["role", "position", "title", "job role"],
        width=26
    ),
    ExcelColumnDefinition(
        key="location",
        canonical_header="Location",
        aliases=["city", "country", "workplace", "region"],
        width=18
    ),
    ExcelColumnDefinition(
        key="job_type",
        canonical_header="Job Type",
        aliases=["employment type", "type", "contract type"],
        width=14
    ),
    ExcelColumnDefinition(
        key="match_score",
        canonical_header="Match Score",
        aliases=["score", "match %", "match", "fit score"],
        width=14
    ),
    ExcelColumnDefinition(
        key="status",
        canonical_header="Status",
        aliases=["application status", "current status", "stage", "state"],
        width=16
    ),
    ExcelColumnDefinition(
        key="resume_used",
        canonical_header="Resume Used",
        aliases=["resume", "cv", "resume variant", "resume file"],
        width=22
    ),
    ExcelColumnDefinition(
        key="source",
        canonical_header="Source",
        aliases=["job board", "platform", "discovered via", "channel"],
        width=16
    ),
    ExcelColumnDefinition(
        key="job_url",
        canonical_header="Job URL",
        aliases=["posting url", "link", "job link", "url"],
        width=25
    ),
    ExcelColumnDefinition(
        key="application_url",
        canonical_header="Application URL",
        aliases=["apply url", "apply link", "direct link"],
        width=25
    ),
    ExcelColumnDefinition(
        key="applied_at",
        canonical_header="Application Date",
        aliases=["applied date", "date applied", "date", "submission date"],
        width=18
    ),
    ExcelColumnDefinition(
        key="last_updated",
        canonical_header="Last Updated",
        aliases=["updated at", "last modified", "modified date"],
        width=18
    ),
    ExcelColumnDefinition(
        key="follow_up_date",
        canonical_header="Follow-up Date",
        aliases=["follow up", "next step date", "reminder"],
        width=16
    ),
    ExcelColumnDefinition(
        key="notes",
        canonical_header="Notes",
        aliases=["comments", "summary", "feedback", "remarks"],
        width=35
    ),
]


def get_canonical_headers() -> List[str]:
    return [col.canonical_header for col in DEFAULT_EXCEL_COLUMNS]


def get_column_alias_map() -> Dict[str, str]:
    """Map lowercase normalized alias -> standard field key."""
    alias_map = {}
    for col in DEFAULT_EXCEL_COLUMNS:
        alias_map[col.canonical_header.lower()] = col.key
        alias_map[col.key.lower()] = col.key
        for alias in col.aliases:
            alias_map[alias.lower()] = col.key
    return alias_map
