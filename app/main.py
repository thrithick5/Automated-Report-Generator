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
    # Startup
    logger.info("Starting application...")
    init_db()
    logger.info("Database initialized")
    
    # Display access URL
    host = "localhost" if settings.app_host == "0.0.0.0" else settings.app_host
    url = f"http://{host}:{settings.app_port}"
    logger.info(f"Application running at: {url}")
    print(f"\n Application running at: {url} \n")
    
    # Start scheduler
    scheduler.start()
    
    # Schedule job if configuration exists
    db = SessionLocal()
    try:
        scheduler.schedule_job(db)
    finally:
        db.close()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    scheduler.stop()


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
