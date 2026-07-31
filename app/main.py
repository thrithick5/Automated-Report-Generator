from pathlib import Path
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, SessionLocal
from app.routers import config, analysis, reports
from app.config import settings
from app.services.scheduler import ReportScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = ReportScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting application...")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    try:
        scheduler.start()
        db = SessionLocal()
        try:
            scheduler.schedule_job(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
    
    yield
    
    try:
        scheduler.stop()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title="AI Code Report Generator",
    description="Automated daily code analysis and reporting system",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(config.router)
app.include_router(analysis.router)
app.include_router(reports.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "scheduler_running": scheduler.scheduler.running
    }


if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )
