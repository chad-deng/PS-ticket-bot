"""
Main FastAPI application for PS Ticket Process Bot.
"""

# Load environment variables first, before any other imports
from dotenv import load_dotenv
load_dotenv()

# Add the project root to Python path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import structlog

# Import version and logging
from app import __version__
from app.core.logging_config import setup_logging

# Setup logging first
setup_logging()
logger = structlog.get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="PS Ticket Process Bot",
    description="JIRA ticket processing bot for Product Support",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {
        "message": "PS Ticket Process Bot",
        "version": __version__,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint accessed")
    return {
        "status": "healthy",
        "version": __version__,
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (placeholder)."""
    # TODO: Implement Prometheus metrics
    return {"metrics": "not_implemented"}


# Include API routers
from app.api import webhooks, admin, quality, ai_comments, jira_operations, logging_api, scheduled_search, scheduler
app.include_router(webhooks.router, prefix="/webhook", tags=["webhooks"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(quality.router, prefix="/quality", tags=["quality"])
app.include_router(ai_comments.router, prefix="/ai", tags=["ai-comments"])
app.include_router(jira_operations.router, prefix="/jira", tags=["jira-operations"])
app.include_router(logging_api.router, prefix="/logs", tags=["logging"])
app.include_router(scheduled_search.router, prefix="/search", tags=["scheduled-search"])
app.include_router(scheduler.router, tags=["scheduler"])


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    # Clear caches to ensure fresh environment variables are loaded
    from app.core.config import clear_settings_cache, reload_settings
    from app.services.jira_client import clear_jira_client_cache
    from app.services.gemini_client import clear_gemini_client_cache
    clear_settings_cache()
    clear_jira_client_cache()
    clear_gemini_client_cache()

    # Force reload settings with fresh environment variables
    settings = reload_settings()

    logger.info(
        "PS Ticket Process Bot starting up",
        version=__version__,
        environment=os.getenv("ENVIRONMENT", "development"),
        jira_url=settings.jira.base_url
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("PS Ticket Process Bot shutting down")


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
