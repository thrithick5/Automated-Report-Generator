from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Configuration, Report
from app.services.git_manager import GitManager
from app.services.analyzer import CodeAnalyzer
from app.services.emailer import EmailService
from datetime import datetime

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


def run_analysis_task(db: Session, config_id: int = 1):
    """Background task to run analysis."""
    try:
        config = db.query(Configuration).filter(Configuration.id == config_id).first()
        if not config:
            raise Exception("Configuration not found")
        
        # Clone/pull repository
        git_manager = GitManager()
        repo_path, _ = git_manager.clone_or_pull(config.repo_url, config.branch)
        
        # Analyze code
        analyzer = CodeAnalyzer()
        analysis_result = analyzer.analyze_code(repo_path)
        
        # Save report
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
        
        # Send email if configured
        if config.recipients:
            recipients = [r.strip() for r in config.recipients.split(',') if r.strip()]
            if recipients:
                emailer = EmailService()
                emailer.send_report(recipients, analysis_result, config.repo_url)
        
    except Exception as e:
        print(f"Analysis task failed: {str(e)}")


@router.post("/now")
def trigger_analysis(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger immediate code analysis."""
    
    config = db.query(Configuration).first()
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found. Please configure settings first.")
    
    # Run analysis in background
    background_tasks.add_task(run_analysis_task, db, config.id)
    
    return {
        "status": "started",
        "message": "Analysis started in background",
        "timestamp": datetime.now().isoformat()
    }
