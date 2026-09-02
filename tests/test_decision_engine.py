"""Tests for the Economic Decision Engine (Milestone 7)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest

from src.database.models import Customer, RecoveryCase
from src.decision.candidates import CandidateActionGenerator
from src.decision.policy import ExpectedValuePolicy
from src.models.recovery_propensity import RecoveryPropensityModel


class MockPropensityModel(RecoveryPropensityModel):
    """Mock propensity model for deterministic deterministic testing."""

    def __init__(self, prob_map: dict[str, float]):
        self.prob_map = prob_map
        self.metadata = {"version": "mock"}

    def load(self) -> None:
        pass

    def _ensure_loaded(self) -> None:
        pass

    def predict(
        self, case: RecoveryCase, customer: Customer, action_type: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Return the pre-configured probability for the given action type."""
        # This explicit check prevents outcome leakage tests from failing, as we only mock known actions
        if action_type not in self.prob_map:
            raise ValueError(f"Mock missing prob for {action_type}")

        return {
            "recovery_probability": self.prob_map[action_type],
            "confidence": 1.0,
            "model_version": "mock_v1",
        }


@pytest.fixture
def mock_case() -> RecoveryCase:
    case = RecoveryCase(amount_at_risk=100.0, status="FAILED", root_cause="INSUFFICIENT_FUNDS")
    case.case_id = uuid.uuid4()
    return case


@pytest.fixture
def mock_customer() -> Customer:
    return Customer(communication_opt_out=False)


def test_scenario_a_high_prob_cheap_action_wins(
    mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Scenario A — High-probability cheap action wins."""
    # NO_ACTION cost=0.00
    # EMAIL_REMINDER cost=0.05
    # SMS_REMINDER cost=0.15
    # RETRY_LATER cost=0.10

    # EMAIL has high prob and is cheap.
    model = MockPropensityModel(
        {
            "RETRY_LATER": 0.5,  # EV = 50 - 0.10 = 49.90
            "EMAIL_REMINDER": 0.6,  # EV = 60 - 0.05 = 59.95
            "SMS_REMINDER": 0.1,  # EV = 10 - 0.15 = 9.85
            "NO_ACTION": 0.0,  # EV = 0
        }
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    assert result.selected_action == "EMAIL_REMINDER"
    assert result.expected_net_recovery == Decimal("59.95")


def test_scenario_b_expensive_action_loses(
    mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Scenario B — Expensive action loses if net EV is lower."""
    # Let's say RETRY_LATER has cost 0.10, EMAIL is 0.05
    # Make RETRY slightly higher prob (0.5002) than EMAIL (0.5000),
    # but the cost difference (0.05) makes EMAIL the better net EV.
    # Amount at risk = 100.
    # EMAIL EV = 50.00 - 0.05 = 49.95
    # RETRY EV = 50.02 - 0.10 = 49.92

    model = MockPropensityModel(
        {"RETRY_LATER": 0.5002, "EMAIL_REMINDER": 0.5000, "SMS_REMINDER": 0.1000, "NO_ACTION": 0.0}
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    assert result.selected_action == "EMAIL_REMINDER"
    assert result.expected_net_recovery == Decimal("49.95")


def test_scenario_c_no_action_fallback(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    """Scenario C — NO_ACTION wins when all EVs are negative."""
    # Very low probabilities, EV < cost
    # For a $100 amount, prob < 0.0005 for EMAIL makes EV < 0.05
    model = MockPropensityModel(
        {
            "RETRY_LATER": 0.0001,  # EV = 0.01 - 0.10 = -0.09
            "EMAIL_REMINDER": 0.0001,  # EV = 0.01 - 0.05 = -0.04
            "SMS_REMINDER": 0.0001,  # EV = 0.01 - 0.15 = -0.14
            "NO_ACTION": 0.0,
        }
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    assert result.selected_action == "NO_ACTION"
    assert result.expected_net_recovery == Decimal("0.00")


def test_scenario_e_already_paid(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    """Scenario E — Already Paid returns NO_ACTION."""
    mock_case.status = "RECOVERED"

    # Even if the model outputs high probability, the generator should block it
    model = MockPropensityModel(
        {"RETRY_LATER": 0.99, "EMAIL_REMINDER": 0.99, "SMS_REMINDER": 0.99, "NO_ACTION": 0.0}
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    assert result.selected_action == "NO_ACTION"

    # Check that others were marked ineligible
    for action in result.ranked_actions:
        if action.action_type != "NO_ACTION":
            assert not action.is_eligible
            assert action.ineligibility_reason == "Case is already paid."


def test_scenario_f_missing_model_fails_safely(
    mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Scenario F — Missing model or prediction failure fails safely to NO_ACTION."""

    class FailingModel(RecoveryPropensityModel):
        def predict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("Model inference failed")

    policy = ExpectedValuePolicy(propensity_model=FailingModel())
    result = policy.evaluate(mock_case, mock_customer)

    assert result.selected_action == "NO_ACTION"
    assert result.expected_net_recovery == Decimal("0.00")


def test_scenario_g_decimal_precision(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    """Scenario G — Financial calculations use exact Decimal arithmetic."""
    # Prob = 0.3, Amount = 100 -> Expected = 30.00
    # Cost = 0.05 -> Net = 29.95
    model = MockPropensityModel(
        {"RETRY_LATER": 0.3, "EMAIL_REMINDER": 0.3, "SMS_REMINDER": 0.3, "NO_ACTION": 0.0}
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    # 30.00 - 0.05 (EMAIL is cheapest, so it wins)
    assert result.selected_action == "EMAIL_REMINDER"
    assert isinstance(result.expected_net_recovery, Decimal)
    assert result.expected_net_recovery == Decimal("29.95")


def test_scenario_h_determinism_and_tie_breaking(
    mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Scenario H & I — Determinism and Tie Breaking."""
    # Ensure stable sorting:
    # 1. Expected Net Recovery (Desc)
    # 2. Probability (Desc)
    # 3. Cost (Asc)
    # 4. Name (Asc)

    # Let's create an artificial tie for Net EV.
    # Action1: Cost 2.00, EV = 11.90 -> Net EV = 9.90 -> P(rec)=0.119
    # Action2: Cost 0.05, EV = 9.95  -> Net EV = 9.90 -> P(rec)=0.0995
    # Since Net EVs are equal, it should fall to Probability (highest wins).
    # Thus, Action1 should win.
    # To map to our real actions:
    # RETRY_LATER: Cost 2.00, P=0.119 -> EV=11.90, NetEV=9.90
    # EMAIL_REMINDER: Cost 0.05, P=0.0995 -> EV=9.95, NetEV=9.90

    model = MockPropensityModel(
        {"RETRY_LATER": 0.119, "EMAIL_REMINDER": 0.0995, "SMS_REMINDER": 0.0, "NO_ACTION": 0.0}
    )
    policy = ExpectedValuePolicy(propensity_model=model)
    result = policy.evaluate(mock_case, mock_customer)

    assert result.expected_net_recovery == Decimal("9.90")
    assert result.selected_action == "RETRY_LATER"  # Won because P(recovery) is higher


def test_scenario_j_leakage_audit(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    """Scenario J — Audit that policy engine does not consume outcome fields."""
    # Let's add outcome fields to the case and ensure they don't break/affect the engine
    mock_case.amount_recovered = 100.0  # type: ignore[attr-defined]

    # The policy interface only requires case and customer.
    # There is no place where outcome or status_after are consumed, because
    # they are not part of the required input mapping. The only place it could
    # leak is if CandidateActionGenerator or ExpectedValuePolicy checks it.

    gen = CandidateActionGenerator()
    candidates = gen.generate(mock_case, mock_customer)

    # Verify the generator doesn't look at amount_recovered
    for c in candidates:
        if c.action_type != "NO_ACTION":
            assert c.is_eligible, "Amount recovered should not make action ineligible"
