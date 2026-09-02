"""Tests for the Recovery Propensity Model and Feature Extractor."""

from typing import Any

import pytest

from src.database.models import Customer, RecoveryCase
from src.features.recovery_features import RecoveryPropensityFeatureExtractor
from src.models.recovery_propensity import RecoveryPropensityModel


@pytest.fixture
def mock_case() -> RecoveryCase:
    return RecoveryCase(
        amount_at_risk=100.0, risk_score=0.7, root_cause="EXPIRED_CARD", root_cause_confidence=0.9
    )


@pytest.fixture
def mock_customer() -> Customer:
    return Customer(
        payment_reliability_score=0.2,
        lifetime_value=500.0,
        active_subscriptions=1,
        avg_payment_delay_days=15.0,
    )


@pytest.fixture
def extractor() -> RecoveryPropensityFeatureExtractor:
    return RecoveryPropensityFeatureExtractor()


def test_recovery_feature_extractor_no_leakage(
    extractor: RecoveryPropensityFeatureExtractor, mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Test that features do not contain outcome leakage."""
    features = extractor.extract(
        case=mock_case, customer=mock_customer, action_type="EMAIL_REMINDER", attempt_number=1
    )

    # Check for obvious forbidden keywords
    forbidden = ["success", "outcome", "status_after", "amount_recovered"]
    for key in features:
        for f in forbidden:
            assert f not in key.lower()


def test_action_aware_features_present(
    extractor: RecoveryPropensityFeatureExtractor, mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Test that the candidate action heavily influences the features."""
    features_email = extractor.extract(
        case=mock_case, customer=mock_customer, action_type="EMAIL_REMINDER", attempt_number=1
    )

    features_retry = extractor.extract(
        case=mock_case, customer=mock_customer, action_type="RETRY_LATER", attempt_number=1
    )

    assert features_email["action_type"] == "EMAIL_REMINDER"
    assert features_retry["action_type"] == "RETRY_LATER"

    # Action interactions
    assert features_email["comm_cust_issue_interaction"] == 1.0  # Email for expired card
    assert features_retry["retry_transient_interaction"] == 0.0  # Retry for expired card is 0


def test_inference_service_handling(monkeypatch: Any) -> None:
    """Test inference contract handles missing model gracefully without crashing badly."""
    model = RecoveryPropensityModel(model_dir="tests/mock_dir_does_not_exist")

    with pytest.raises(FileNotFoundError):
        model.load()
