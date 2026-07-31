from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Configuration, Report
from app.services.git_manager import GitManager
from app.services.analyzer import CodeAnalyzer
from app.services.emailer import EmailService
import logging

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Manages scheduled report generation."""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.git_manager = GitManager()
        self.analyzer = CodeAnalyzer()
        self.emailer = EmailService()
    
    def run_analysis_job(self, db: Session, config_id: int = 1):
        """
        Execute the full analysis pipeline.
        
        Args:
            db: Database session
            config_id: Configuration ID to use
        """
        try:
            logger.info(f"Starting scheduled analysis job at {datetime.now()}")
            
            # Get configuration
            config = db.query(Configuration).filter(Configuration.id == config_id).first()
            if not config:
                logger.error("No configuration found")
                return
            
            # Clone/pull repository
            logger.info(f"Fetching repository: {config.repo_url}")
            repo_path, is_new = self.git_manager.clone_or_pull(config.repo_url, config.branch)
            
            # Analyze code
            logger.info("Analyzing code...")
            analysis_result = self.analyzer.analyze_code(repo_path)
            
            # Save report to database
            report = Report(
                repo_url=config.repo_url,
                summary=analysis_result.get('summary', ''),
                critical_count=analysis_result.get('metrics', {}).get('critical', 0),
                warning_count=analysis_result.get('metrics', {}).get('warnings', 0),
                complexity_score=analysis_result.get('metrics', {}).get('complexity', 0),
                quality_score=analysis_result.get('metrics', {}).get('quality_score', 0),
                full_report=analysis_result
            )
            db.add(report)
            db.commit()
            logger.info(f"Report saved with ID: {report.id}")
            
            # Send email
            if config.recipients:
                recipients = [r.strip() for r in config.recipients.split(',') if r.strip()]
                if recipients:
                    logger.info(f"Sending email to {len(recipients)} recipients")
                    self.emailer.send_report(recipients, analysis_result, config.repo_url)
            
            logger.info("Analysis job completed successfully")
            
        except Exception as e:
            logger.error(f"Analysis job failed: {str(e)}")
    
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
            func=lambda: self.run_analysis_job(db, config_id),
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
