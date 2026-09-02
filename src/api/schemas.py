"""Health check endpoint schemas and response models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for the /health endpoint."""

    status: str = Field(description="Application health status")
    app_name: str = Field(description="Application name")
    version: str = Field(description="Application version")
    timestamp: datetime = Field(description="Current server time in UTC")

    @classmethod
    def ok(cls, app_name: str, version: str) -> HealthResponse:
        """Create a healthy response."""
        return cls(
            status="ok",
            app_name=app_name,
            version=version,
            timestamp=datetime.now(UTC),
        )
