import decimal
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import joblib
import numpy as np

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment
from src.database.models import Customer, Payment, RecoveryCase
from src.features.root_cause_features import RootCauseFeatureExtractor
from src.models.root_cause_inference import RootCauseInferenceService
from src.models.root_cause_rules import DeterministicRootCauseMapper


def test_deterministic_mapping_rules() -> None:
    mapper = DeterministicRootCauseMapper()

    # Invoice mapping
    res = mapper.map_root_cause(source_type="invoice")
    assert res is not None
    assert res == ("OVERDUE_INVOICE", 1.0, True)

    # Provider code mapping
    res = mapper.map_root_cause(source_type="payment", failure_code="ERR_EXPIRED_101")
    assert res is not None
    assert res == ("EXPIRED_CARD", 1.0, True)

    # Generic / ambiguous failure code falls through
    res = mapper.map_root_cause(source_type="payment", failure_code="ERR_GENERIC_901")
    assert res is None


def test_root_cause_feature_extractor_no_leakage() -> None:
    c = Customer(
        customer_id=uuid.uuid4(),
        customer_since=datetime.now(UTC) - timedelta(days=200),
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
    p_future = Payment(
        payment_id=uuid.uuid4(),
        customer_id=c.customer_id,
        amount=decimal.Decimal("50.0"),
        created_at=datetime.now(UTC) + timedelta(days=2),
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

    extractor = RootCauseFeatureExtractor(
        customers=[c],
        payments=[p, p_future],
        cases=[case],
    )
    features = extractor.extract_features(case)

    # Assert point-in-time safety: p_future is excluded
    assert features["failures_last_30d"] == 0
    assert features["historical_success_rate"] == 1.0
    assert "root_cause" not in features
    assert "failure_code" not in features
    assert features["amount_to_ltv_ratio"] == 0.5
    assert features["customer_age_days"] >= 199

    # Assert cyclic encodings
    assert -1.0 <= features["hour_sin"] <= 1.0
    assert -1.0 <= features["hour_cos"] <= 1.0
    assert -1.0 <= features["weekday_sin"] <= 1.0
    assert -1.0 <= features["weekday_cos"] <= 1.0


class MockPipeline:
    def predict_proba(self, x: Any) -> np.ndarray:
        return np.array([[0.1, 0.85, 0.05]])


class MockLabelEncoder:
    def inverse_transform(self, idxs: list[int]) -> list[str]:
        mapping = {0: "GATEWAY_FAILURE", 1: "NETWORK_TIMEOUT", 2: "UNKNOWN"}
        return [mapping[i] for i in idxs]


def test_inference_service_hybrid() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.joblib")
        metadata_path = os.path.join(tmpdir, "metadata.json")

        joblib.dump({"pipeline": MockPipeline(), "label_encoder": MockLabelEncoder()}, model_path)

        metadata = {
            "model_name": "root_cause",
            "model_version": "1.0.0",
            "feature_schema": ["amount", "hour"],
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        service = RootCauseInferenceService(model_path=model_path, metadata_path=metadata_path)

        # 1. Deterministic path
        det_result = service.diagnose(source_type="invoice")
        assert det_result["root_cause"] == "OVERDUE_INVOICE"
        assert det_result["confidence"] == 1.0
        assert det_result["is_deterministic"] is True
        assert "top_predictions" in det_result
        assert "confidence_status" in det_result
        assert det_result["confidence_status"] == "HIGH"

        # 2. ML Fallback path
        ml_result = service.diagnose(
            source_type="payment",
            failure_code="ERR_GENERIC_950",
            features={"amount": 100.0, "hour": 14},
        )
        assert ml_result["root_cause"] == "NETWORK_TIMEOUT"
        assert ml_result["confidence"] == 0.85
        assert ml_result["is_deterministic"] is False
        assert 0.0 <= ml_result["confidence"] <= 1.0
        assert "top_predictions" in ml_result
        assert len(ml_result["top_predictions"]) >= 1
        assert "confidence_status" in ml_result
        assert ml_result["confidence_status"] in ("HIGH", "MEDIUM", "LOW")


def test_prediction_output_schema() -> None:
    """Verify prediction output contains all required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.joblib")
        metadata_path = os.path.join(tmpdir, "metadata.json")

        joblib.dump({"pipeline": MockPipeline(), "label_encoder": MockLabelEncoder()}, model_path)

        metadata = {
            "model_name": "root_cause",
            "model_version": "1.0.0",
            "feature_schema": ["amount", "hour"],
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        service = RootCauseInferenceService(model_path=model_path, metadata_path=metadata_path)

        # Deterministic result schema
        det = service.diagnose(source_type="invoice")
        required_keys = {
            "root_cause",
            "confidence",
            "top_predictions",
            "confidence_status",
            "model_name",
            "model_version",
            "is_deterministic",
        }
        assert required_keys.issubset(set(det.keys()))

        # ML fallback result schema
        ml = service.diagnose(
            source_type="payment",
            failure_code="ERR_GENERIC_950",
            features={"amount": 100.0, "hour": 14},
        )
        assert required_keys.issubset(set(ml.keys()))

        # Top predictions structure
        for pred in ml["top_predictions"]:
            assert "root_cause" in pred
            assert "probability" in pred
            assert isinstance(pred["probability"], float)


def test_top_k_ordering() -> None:
    """Verify top predictions are sorted by probability descending."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.joblib")
        metadata_path = os.path.join(tmpdir, "metadata.json")

        joblib.dump({"pipeline": MockPipeline(), "label_encoder": MockLabelEncoder()}, model_path)

        metadata = {
            "model_name": "root_cause",
            "model_version": "1.0.0",
            "feature_schema": ["amount", "hour"],
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        service = RootCauseInferenceService(model_path=model_path, metadata_path=metadata_path)
        result = service.diagnose(
            source_type="payment",
            failure_code="ERR_GENERIC_950",
            features={"amount": 100.0, "hour": 14},
        )

        preds = result["top_predictions"]
        probs = [p["probability"] for p in preds]
        assert probs == sorted(probs, reverse=True), "Top predictions must be sorted descending"


def test_deterministic_inference_consistency() -> None:
    """Verify inference is deterministic (same input → same output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.joblib")
        metadata_path = os.path.join(tmpdir, "metadata.json")

        joblib.dump({"pipeline": MockPipeline(), "label_encoder": MockLabelEncoder()}, model_path)

        metadata = {
            "model_name": "root_cause",
            "model_version": "1.0.0",
            "feature_schema": ["amount", "hour"],
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        service = RootCauseInferenceService(model_path=model_path, metadata_path=metadata_path)

        result1 = service.diagnose(
            source_type="payment",
            failure_code="ERR_GENERIC_950",
            features={"amount": 100.0, "hour": 14},
        )
        result2 = service.diagnose(
            source_type="payment",
            failure_code="ERR_GENERIC_950",
            features={"amount": 100.0, "hour": 14},
        )

        assert result1["root_cause"] == result2["root_cause"]
        assert result1["confidence"] == result2["confidence"]


def test_no_future_feature_usage() -> None:
    """Verify that feature extractor does not use future information."""
    c = Customer(
        customer_id=uuid.uuid4(),
        customer_since=datetime.now(UTC) - timedelta(days=100),
        active_subscriptions=1,
        lifetime_value=decimal.Decimal("500.0"),
        payment_reliability_score=decimal.Decimal("0.8"),
    )
    # Past payment
    p_past = Payment(
        payment_id=uuid.uuid4(),
        customer_id=c.customer_id,
        amount=decimal.Decimal("30.0"),
        created_at=datetime.now(UTC) - timedelta(days=5),
        status="failed",
    )
    # Future payment (should be excluded)
    p_future = Payment(
        payment_id=uuid.uuid4(),
        customer_id=c.customer_id,
        amount=decimal.Decimal("60.0"),
        created_at=datetime.now(UTC) + timedelta(days=10),
        status="failed",
    )
    case = RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=c.customer_id,
        source_type="payment",
        source_id=p_past.payment_id,
        amount_at_risk=decimal.Decimal("30.0"),
        status="CREATED",
        created_at=datetime.now(UTC),
    )

    extractor = RootCauseFeatureExtractor(
        customers=[c],
        payments=[p_past, p_future],
        cases=[case],
    )
    features = extractor.extract_features(case)

    # Future payment must not contribute to failure counts
    assert features["failure_count"] == 1  # Only p_past
    assert features["failures_last_7d"] == 1
    assert "root_cause" not in features
    assert "failure_code" not in features


def test_contextual_relationships_statistical() -> None:
    """Statistically verify that synthetic generation contextual relationships exist."""
    env = SyntheticEnvironment(GenerationConfig(seed=42))
    data = env.generate()

    failed_payments = [p for p in data["payments"] if p.status == "failed"]
    cust_map = {c.customer_id: c for c in data["customers"]}

    # 1. Card Expired rate vs Customer Age
    older_card_expired = sum(
        1
        for p in failed_payments
        if p.payment_method == "card"
        and (p.occurred_at.date() - cust_map[p.customer_id].customer_since.date()).days > 180
        and p.failure_reason == "EXPIRED_CARD"
    )
    older_card_total = sum(
        1
        for p in failed_payments
        if p.payment_method == "card"
        and (p.occurred_at.date() - cust_map[p.customer_id].customer_since.date()).days > 180
    )
    older_expired_rate = older_card_expired / older_card_total if older_card_total > 0 else 0

    newer_card_expired = sum(
        1
        for p in failed_payments
        if p.payment_method == "card"
        and (p.occurred_at.date() - cust_map[p.customer_id].customer_since.date()).days <= 60
        and p.failure_reason == "EXPIRED_CARD"
    )
    newer_card_total = sum(
        1
        for p in failed_payments
        if p.payment_method == "card"
        and (p.occurred_at.date() - cust_map[p.customer_id].customer_since.date()).days <= 60
    )
    newer_expired_rate = newer_card_expired / newer_card_total if newer_card_total > 0 else 0

    # Older customer accounts must have a higher EXPIRED_CARD rate than newer accounts
    assert older_expired_rate > newer_expired_rate

    # 2. Insufficient funds rate vs payment reliability
    low_rel_nsf_count = sum(
        1
        for p in failed_payments
        if (cust_map[p.customer_id].payment_reliability_score or 0) < 0.4
        and p.failure_reason == "INSUFFICIENT_FUNDS"
    )
    high_rel_nsf_count = sum(
        1
        for p in failed_payments
        if (cust_map[p.customer_id].payment_reliability_score or 0) > 0.8
        and p.failure_reason == "INSUFFICIENT_FUNDS"
    )

    low_rel_total = sum(
        1 for p in failed_payments if (cust_map[p.customer_id].payment_reliability_score or 0) < 0.4
    )
    high_rel_total = sum(
        1 for p in failed_payments if (cust_map[p.customer_id].payment_reliability_score or 0) > 0.8
    )

    low_rel_nsf_rate = low_rel_nsf_count / low_rel_total if low_rel_total > 0 else 0
    high_rel_nsf_rate = high_rel_nsf_count / high_rel_total if high_rel_total > 0 else 0

    assert low_rel_nsf_rate > high_rel_nsf_rate
