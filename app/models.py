from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class Configuration(Base):
    """Stores repository and email configuration."""
    __tablename__ = "configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, nullable=False)
    branch = Column(String, default="main")
    analysis_model = Column(String, default="gemini1.5flash")
    recipients = Column(Text)  # Comma-separated email addresses
    schedule_time = Column(String, default="09:00")
    frequency = Column(String, default="daily")  # daily, weekly, biweekly
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    """Stores analysis reports."""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    repo_url = Column(String)
    summary = Column(Text)
    critical_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    complexity_score = Column(Integer, default=0)
    quality_score = Column(Integer, default=0)
    full_report = Column(JSON)  # Complete JSON report from Gemini
    created_at = Column(DateTime, default=datetime.utcnow)
