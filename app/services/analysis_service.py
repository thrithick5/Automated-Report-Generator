import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AnalysisRun, Configuration, Report
from app.services.analyzer import CodeAnalyzer
from app.services.emailer import EmailService
from app.services.git_manager import GitManager

logger = logging.getLogger(__name__)


def _new_run(db: Session, repo_url: str = "", branch: str = "") -> AnalysisRun:
    run = AnalysisRun(status="running", repo_url=repo_url, branch=branch)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run(db: Session, run: AnalysisRun, status: str, error: str = "",
                email_sent: bool = False, report_id: int = None) -> None:
    run.status = status
    run.error_message = error or None
    run.email_sent = 1 if email_sent else 0
    run.report_id = report_id
    run.finished_at = datetime.utcnow()
    db.commit()


def run_analysis(db: Session, config_id: int = 1, send_email: bool = True) -> dict:
    """Run the full analysis pipeline synchronously.

    Creates/updates an AnalysisRun row so status and history are trackable
    (needed because serverless platforms do not support background tasks).

    Returns:
        dict: result with status, report_id, error, email_sent
    """
    result = {"status": "failed", "error": None, "report_id": None, "email_sent": False}

    # Guard against overlapping runs. A run stuck in "running" for a long time
    # is a stale row left behind by a killed serverless function (e.g. a
    # Vercel timeout), so it is marked failed and the pipeline proceeds.
    running = db.query(AnalysisRun).filter(AnalysisRun.status == "running").first()
    if running:
        stale_for = timedelta(minutes=30)
        started = running.started_at or datetime.utcnow()
        if datetime.utcnow() - started < stale_for:
            return {
                "status": "already_running",
                "error": "An analysis is already in progress.",
                "report_id": None,
                "email_sent": False,
            }
        logger.warning("Marking stale run #%s as failed", running.id)
        running.status = "failed"
        running.error_message = ("Marked failed: a previous run was interrupted "
                                 "(likely a platform timeout).")
        running.finished_at = datetime.utcnow()
        db.commit()

    config = db.query(Configuration).filter(Configuration.id == config_id).first()
    if not config:
        return {
            "status": "failed",
            "error": "No configuration found. Please configure settings first.",
            "report_id": None,
            "email_sent": False,
        }

    run = _new_run(db, config.repo_url, config.branch)

    try:
        logger.info(f"Fetching repository: {config.repo_url}")
        git_manager = GitManager()
        repo_path, _ = git_manager.fetch(config.repo_url, config.branch)

        logger.info("Analyzing code...")
        analyzer = CodeAnalyzer()
        analysis_result = analyzer.analyze_code(repo_path)

        report = Report(
            repo_url=config.repo_url,
            summary=analysis_result.get('summary', ''),
            critical_count=analysis_result.get('metrics', {}).get('critical', 0),
            warning_count=analysis_result.get('metrics', {}).get('warnings', 0),
            complexity_score=analysis_result.get('metrics', {}).get('complexity', 0),
            quality_score=analysis_result.get('metrics', {}).get('quality_score', 0),
            full_report=analysis_result,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        logger.info(f"Report saved with ID: {report.id}")

        email_sent = False
        recipients = _parse_recipients(config.recipients)
        if send_email and recipients:
            logger.info(f"Sending email to {len(recipients)} recipients")
            emailer = EmailService()
            email_sent, email_err = emailer.send_report(recipients, analysis_result, config.repo_url)
            if not email_sent:
                logger.error(f"Email sending failed: {email_err}")

        _finish_run(db, run, "success", email_sent=email_sent, report_id=report.id)
        return {
            "status": "success",
            "error": None,
            "report_id": report.id,
            "email_sent": email_sent,
            "recipients": len(recipients) if email_sent else 0,
        }

    except Exception as e:
        logger.exception("Analysis run failed")
        _finish_run(db, run, "failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
            "report_id": None,
            "email_sent": False,
        }


def _parse_recipients(raw: str) -> list:
    if not raw:
        return []
    return [r.strip() for r in raw.split(',') if r.strip()]


def is_run_due(config: Configuration, now: datetime = None) -> bool:
    """Check whether a scheduled analysis is due at this exact time.

    Matches the frequency/time configured in the UI so a single Vercel cron
    (running every few minutes) can support daily, weekly, and biweekly
    schedules without a persistent scheduler.
    """
    now = now or datetime.now()
    try:
        hour, minute = map(int, config.schedule_time.split(':'))
    except (ValueError, AttributeError):
        return False

    if (now.hour, now.minute) != (hour, minute):
        return False

    if config.frequency == 'weekly':
        return now.weekday() == 0  # Monday
    if config.frequency == 'biweekly':
        # Every other Monday (ISO week parity approximation).
        return now.weekday() == 0 and now.isocalendar()[1] % 2 == 0
    return True  # daily (default)
