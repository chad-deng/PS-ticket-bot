"""
Main FastAPI application for PS Ticket Process Bot.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Import version
from app import __version__

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
    return {
        "message": "PS Ticket Process Bot",
        "version": __version__,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
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
from app.api import webhooks
app.include_router(webhooks.router, prefix="/webhook", tags=["webhooks"])


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
