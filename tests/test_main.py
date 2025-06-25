"""
Tests for the main FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestMainEndpoints:
    """Test cases for main application endpoints."""

    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "PS Ticket Process Bot"
        assert "version" in data
        assert data["status"] == "running"

    def test_health_check(self):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data

    def test_metrics_endpoint(self):
        """Test the metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data

    def test_app_startup(self):
        """Test that the application starts correctly."""
        # This test ensures the app can be imported and initialized
        assert app is not None
        assert hasattr(app, 'routes')
        assert len(app.routes) > 0
