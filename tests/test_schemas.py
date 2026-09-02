"""Tests for API response schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from src.api.schemas import HealthResponse


class TestHealthResponseSchema:
    """Tests for the HealthResponse Pydantic model."""

    def test_ok_factory_creates_valid_response(self) -> None:
        """HealthResponse.ok() should create a valid response."""
        resp = HealthResponse.ok(app_name="REVIVE", version="0.1.0")
        assert resp.status == "ok"
        assert resp.app_name == "REVIVE"
        assert resp.version == "0.1.0"
        assert isinstance(resp.timestamp, datetime)

    def test_timestamp_is_utc(self) -> None:
        """The timestamp in HealthResponse should be in UTC."""
        resp = HealthResponse.ok(app_name="REVIVE", version="0.1.0")
        assert resp.timestamp.tzinfo is not None
        assert resp.timestamp.tzinfo == UTC

    def test_serialization_round_trip(self) -> None:
        """HealthResponse should serialize to and from JSON correctly."""
        resp = HealthResponse.ok(app_name="REVIVE", version="0.1.0")
        json_data = resp.model_dump_json()
        restored = HealthResponse.model_validate_json(json_data)
        assert restored.status == resp.status
        assert restored.app_name == resp.app_name
        assert restored.version == resp.version
