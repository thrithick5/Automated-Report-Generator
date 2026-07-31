from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Configuration
from typing import Optional

router = APIRouter(prefix="/api/config", tags=["configuration"])


class ConfigRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    analysis_model: str = "gemini1.5flash"
    recipients: str
    schedule_time: str = "09:00"
    frequency: str = "daily"


class ConfigResponse(BaseModel):
    id: int
    repo_url: str
    branch: str
    analysis_model: str
    recipients: str
    schedule_time: str
    frequency: str
    
    class Config:
        from_attributes = True


@router.post("/", response_model=ConfigResponse)
def save_configuration(config: ConfigRequest, db: Session = Depends(get_db)):
    """Save or update configuration settings."""
    
    # Check if configuration exists
    existing_config = db.query(Configuration).first()
    
    if existing_config:
        # Update existing
        existing_config.repo_url = config.repo_url
        existing_config.branch = config.branch
        existing_config.analysis_model = config.analysis_model
        existing_config.recipients = config.recipients
        existing_config.schedule_time = config.schedule_time
        existing_config.frequency = config.frequency
        db.commit()
        db.refresh(existing_config)
        return existing_config
    else:
        # Create new
        new_config = Configuration(**config.dict())
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        return new_config


@router.get("/", response_model=Optional[ConfigResponse])
def get_configuration(db: Session = Depends(get_db)):
    """Get current configuration settings."""
    config = db.query(Configuration).first()
    return config
