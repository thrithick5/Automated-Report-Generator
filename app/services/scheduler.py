from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Configuration
from app.services.analysis_service import run_analysis
import logging

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Manages scheduled report generation (local/long-running processes only).

    On serverless platforms (Vercel) the scheduler is disabled and scheduled
    runs are triggered by the Vercel Cron Job calling /api/analyze/cron.
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def run_analysis_job(self, config_id: int = 1):
        """Execute the full analysis pipeline via the shared service using a fresh DB session."""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            logger.info(f"Starting scheduled analysis job at {datetime.now()}")
            result = run_analysis(db, config_id)
            logger.info(f"Analysis job finished: {result}")
        except Exception as e:
            logger.error(f"Scheduled analysis job failed: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def schedule_job(self, db: Session, config_id: int = 1):
        """
        Schedule the analysis job based on configuration.
        
        Args:
            db: Database session
            config_id: Configuration ID
        """
        config = db.query(Configuration).filter(Configuration.id == config_id).first()
        if not config:
            logger.warning("No configuration found for scheduling")
            return
        
        # Remove existing jobs
        self.scheduler.remove_all_jobs()
        
        # Parse time (format: "HH:MM")
        hour, minute = map(int, config.schedule_time.split(':'))
        
        # Create cron trigger based on frequency
        if config.frequency == 'daily':
            trigger = CronTrigger(hour=hour, minute=minute)
        elif config.frequency == 'weekly':
            trigger = CronTrigger(day_of_week='mon', hour=hour, minute=minute)
        elif config.frequency == 'biweekly':
            # Run every other Monday (approximation)
            trigger = CronTrigger(day_of_week='mon', hour=hour, minute=minute, week='*/2')
        else:
            trigger = CronTrigger(hour=hour, minute=minute)
        
        # Add job
        self.scheduler.add_job(
            func=self.run_analysis_job,
            args=[config_id],
            trigger=trigger,
            id='analysis_job',
            replace_existing=True
        )
        
        logger.info(f"Scheduled {config.frequency} analysis at {config.schedule_time}")
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
