"""Tests for the /health endpoint and application startup."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI application."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """The health endpoint should return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        """The health response should contain status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_app_name(self, client: TestClient) -> None:
        """The health response should contain the application name."""
        response = client.get("/health")
        data = response.json()
        assert data["app_name"] == "REVIVE"

    def test_health_returns_version(self, client: TestClient) -> None:
        """The health response should contain a version string."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_returns_timestamp(self, client: TestClient) -> None:
        """The health response should contain a UTC timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_health_response_content_type(self, client: TestClient) -> None:
        """The health endpoint should return JSON content type."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestErrorHandling:
    """Tests for global error handling."""

    def test_not_found_returns_404(self, client: TestClient) -> None:
        """Unknown routes should return 404."""
        response = client.get("/nonexistent-route")
        assert response.status_code == 404

    def test_method_not_allowed_returns_405(self, client: TestClient) -> None:
        """Wrong HTTP method on /health should return 405."""
        response = client.post("/health")
        assert response.status_code == 405
