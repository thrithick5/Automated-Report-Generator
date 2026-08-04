from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Report
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportResponse(BaseModel):
    id: int
    timestamp: datetime
    repo_url: str
    summary: str
    critical_count: int
    warning_count: int
    complexity_score: int
    quality_score: int
    full_report: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


@router.get("/latest", response_model=Optional[ReportResponse])
def get_latest_report(db: Session = Depends(get_db)):
    """Get the most recent analysis report."""
    report = db.query(Report).order_by(Report.timestamp.desc()).first()
    return report


@router.get("/", response_model=List[ReportResponse])
def get_all_reports(limit: int = 10, db: Session = Depends(get_db)):
    """Get list of recent reports."""
    reports = db.query(Report).order_by(Report.timestamp.desc()).limit(limit).all()
    return reports


@router.get("/{report_id}", response_model=ReportResponse)
def get_report_by_id(report_id: int, db: Session = Depends(get_db)):
    """Get a specific report by ID."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
