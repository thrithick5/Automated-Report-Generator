from pathlib import Path
import sys
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Serverless platforms (Vercel/Lambda) are ephemeral and cannot run background
# schedulers, so the in-process scheduler is only started on long-running hosts.
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Global scheduler instance (created lazily in lifespan)
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting application...")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    global scheduler
    if IS_SERVERLESS:
        logger.info("Scheduler disabled: running on serverless platform")
    else:
        # Display access URL when running locally
        host = "localhost" if settings.app_host == "0.0.0.0" else settings.app_host
        url = f"http://{host}:{settings.app_port}"
        logger.info(f"Application running at: {url}")
        print(f"\n Application running at: {url} \n")
        
        try:
            scheduler = ReportScheduler()
            scheduler.start()
            db = SessionLocal()
            try:
                scheduler.schedule_job(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
    
    yield
    
    if scheduler is not None:
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

# Enable CORS for frontend deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific Vercel domains in production if desired
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(config.router)
app.include_router(analysis.router)
app.include_router(reports.router)

# Mount static files if directory exists
static_dir = Path("static")
if static_dir.exists() and static_dir.is_dir():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page if static files exist, else return API status."""
    if static_dir.exists() and (static_dir / "index.html").exists():
        return FileResponse(static_dir / "index.html")
    return {"status": "healthy", "message": "AI Code Report Generator API is running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "scheduler_running": bool(scheduler is not None and scheduler.scheduler.running)
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
