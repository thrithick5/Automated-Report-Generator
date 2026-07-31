import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AnalysisRun, Configuration, Report
from app.services.analysis_service import _parse_recipients, is_run_due, run_analysis
from app.services.emailer import EmailService
from app.config import settings
from datetime import datetime

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


def _require_cron_secret(request: Request) -> None:
    """Vercel Cron Jobs send `Authorization: Bearer $CRON_SECRET`."""
    if settings.cron_secret:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.cron_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized cron invocation")


def _is_serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@router.post("/now")
def trigger_analysis(db: Session = Depends(get_db)):
    """Trigger an immediate code analysis (synchronously)."""
    result = run_analysis(db)
    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("error") or "Analysis failed")
    return result


@router.post("/cron")
def cron_analysis(request: Request, db: Session = Depends(get_db)):
    """Vercel Cron Job entrypoint. Protected by CRON_SECRET when configured.

    Runs only when the configured schedule is due, so a single cron entry can
    serve daily/weekly/biweekly schedules set in the UI.
    """
    _require_cron_secret(request)

    config = db.query(Configuration).first()
    if not config:
        return {"status": "skipped", "message": "No configuration found. Configure settings first."}

    if not is_run_due(config):
        return {"status": "skipped", "message": "Not scheduled for this time."}

    return run_analysis(db, config.id)


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Return the latest run status plus a summary of the current config."""
    run = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).first()
    config = db.query(Configuration).first()

    last_run = None
    if run:
        last_run = {
            "id": run.id,
            "status": run.status,
            "repo_url": run.repo_url,
            "branch": run.branch,
            "error_message": run.error_message,
            "email_sent": bool(run.email_sent),
            "report_id": run.report_id,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

    return {
        "configured": bool(config),
        "repo_url": config.repo_url if config else None,
        "branch": config.branch if config else None,
        "recipients": _parse_recipients(config.recipients) if config else [],
        "frequency": config.frequency if config else None,
        "schedule_time": config.schedule_time if config else None,
        "last_run": last_run,
        "serverless": _is_serverless(),
    }


@router.get("/runs")
def get_run_history(limit: int = 20, db: Session = Depends(get_db)):
    """Return recent analysis run history."""
    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).limit(limit).all()
    return [
        {
            "id": run.id,
            "status": run.status,
            "repo_url": run.repo_url,
            "branch": run.branch,
            "error_message": run.error_message,
            "email_sent": bool(run.email_sent),
            "report_id": run.report_id,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }
        for run in runs
    ]


@router.post("/send-email")
def resend_report_email(db: Session = Depends(get_db)):
    """Re-send the latest report to the configured recipients."""
    report = db.query(Report).order_by(Report.timestamp.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report available yet. Run an analysis first.")

    config = db.query(Configuration).first()
    recipients = _parse_recipients(config.recipients) if config else []
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients configured.")

    emailer = EmailService()
    sent = emailer.send_report(recipients, report.full_report, report.repo_url)
    if not sent:
        raise HTTPException(status_code=500, detail="Email sending failed. Check SMTP settings.")
    return {
        "status": "sent",
        "recipients": len(recipients),
        "report_id": report.id,
        "timestamp": datetime.utcnow().isoformat(),
    }
