import json
import os
import tempfile
from typing import Any

import pytest

from src.features.risk_features import RiskFeatureExtractor
from src.models.inference import RiskInferenceService


def test_feature_extractor_no_leakage() -> None:
    import decimal
    import uuid
    from datetime import UTC, datetime, timedelta

    from src.database.models import Customer, Payment, RecoveryCase

    c = Customer(
        customer_id=uuid.uuid4(),
        customer_since=datetime.now(UTC),
        active_subscriptions=1,
        lifetime_value=decimal.Decimal("100.0"),
        payment_reliability_score=decimal.Decimal("0.9"),
    )
    p = Payment(
        payment_id=uuid.uuid4(),
        customer_id=c.customer_id,
        amount=decimal.Decimal("50.0"),
        created_at=datetime.now(UTC) - timedelta(days=2),
        status="successful",
    )
    p2 = Payment(
        payment_id=uuid.uuid4(),
        customer_id=c.customer_id,
        amount=decimal.Decimal("50.0"),
        created_at=datetime.now(UTC) + timedelta(days=2),  # Future payment
        status="failed",
    )
    case = RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=c.customer_id,
        source_type="payment",
        source_id=p.payment_id,
        amount_at_risk=decimal.Decimal("50.0"),
        status="CREATED",
        created_at=datetime.now(UTC),
    )

    extractor = RiskFeatureExtractor(customers=[c], payments=[p, p2], cases=[case])

    features = extractor.extract_features(case)
    # The future payment p2 should NOT be included in failures_last_30d
    assert features["failures_last_30d"] == 0
    assert features["historical_success_rate"] == 1.0


class MockModel:
    def predict_proba(self, x: Any) -> Any:
        import numpy as np

        return np.array([[0.1, 0.9]])

    def predict(self, x: Any) -> Any:
        import numpy as np

        return np.array([1.0])


def test_inference_service_missing_features() -> None:
    # Create dummy artifact files
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.joblib")
        metadata_path = os.path.join(tmpdir, "metadata.json")

        import joblib

        joblib.dump(MockModel(), model_path)

        metadata = {
            "model_name": "revenue_risk",
            "model_version": "1.0.0",
            "configuration": {"features": ["amount", "hour"]},
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        service = RiskInferenceService(model_path=model_path, metadata_path=metadata_path)

        # Test valid features
        result = service.predict({"amount": 100.0, "hour": 12})
        assert result["prediction"] == 1.0
        assert result["confidence"] == 0.9
        assert result["model_name"] == "revenue_risk"

        # Test missing feature
        with pytest.raises(ValueError, match="Missing required feature: hour"):
            service.predict({"amount": 100.0})


def test_inference_service_invalid_path() -> None:
    with pytest.raises(FileNotFoundError):
        RiskInferenceService(model_path="nonexistent.joblib", metadata_path="nonexistent.json")
