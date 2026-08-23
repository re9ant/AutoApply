from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    workplace_type = Column(String(50), default="Unknown")
    employment_type = Column(String(50), default="Full-time")
    experience_years_min = Column(Integer, nullable=True)
    primary_engine = Column(String(100), nullable=True)
    primary_language = Column(String(100), nullable=True)
    job_url = Column(String(1024), nullable=True, unique=True)
    raw_jd_text = Column(Text, nullable=True)
    structured_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ApplicationModel(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String(64), unique=True, nullable=False, index=True)
    company = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    job_url = Column(String(1024), nullable=True)
    application_url = Column(String(1024), nullable=True)
    match_score = Column(Float, nullable=True)
    status = Column(String(50), default="DISCOVERED", nullable=False)
    resume_used = Column(String(255), nullable=True)
    cover_letter = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    score_breakdown = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    applied_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)
