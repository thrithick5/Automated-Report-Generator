import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models import AnalysisRun, Configuration, Report
from app.services.analysis_service import _parse_recipients, is_run_due, run_analysis
from app.services.emailer import EmailService
from app.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


def _require_cron_secret(request: Request) -> None:
    """Vercel Cron Jobs send `Authorization: Bearer $CRON_SECRET`."""
    if settings.cron_secret:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.cron_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized cron invocation")


def _is_serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def run_analysis_in_background(config_id: int):
    """Wrapper function to execute analysis using a dedicated db session."""
    db = SessionLocal()
    try:
        run_analysis(db, config_id=config_id)
    except Exception as e:
        logger.error(f"Background analysis failed: {e}")
    finally:
        db.close()


@router.post("/now")
def trigger_analysis(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger an immediate code analysis in the background."""
    config = db.query(Configuration).first()
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found. Save settings first.")

    # Guard against overlapping runs
    running = db.query(AnalysisRun).filter(AnalysisRun.status == "running").first()
    if running:
        from datetime import timedelta
        stale_for = timedelta(minutes=30)
        started = running.started_at or datetime.utcnow()
        if datetime.utcnow() - started < stale_for:
            return {"status": "running", "message": "Analysis is already in progress"}
        else:
            logger.warning(f"Marking stale run #{running.id} as failed")
            running.status = "failed"
            running.error_message = "Marked failed: interrupted."
            running.finished_at = datetime.utcnow()
            db.commit()

    # Launch background task
    background_tasks.add_task(run_analysis_in_background, config.id)
    return {"status": "running", "message": "Analysis started in background"}


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
    sent, error_msg = emailer.send_report(recipients, report.full_report, report.repo_url)
    if not sent:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {error_msg or 'Check SMTP settings'}")
    return {
        "status": "sent",
        "recipients": len(recipients),
        "report_id": report.id,
        "timestamp": datetime.utcnow().isoformat(),
    }
