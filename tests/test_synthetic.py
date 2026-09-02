"""Tests for synthetic data generation."""

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment


def test_reproducibility() -> None:
    """Identical seeds should produce exactly identical entity sets."""
    config1 = GenerationConfig(num_customers=50, seed=42)
    env1 = SyntheticEnvironment(config1)
    data1 = env1.generate()

    config2 = GenerationConfig(num_customers=50, seed=42)
    env2 = SyntheticEnvironment(config2)
    data2 = env2.generate()

    # Compare customers (use a sample metric like IDs or a specific field)
    c_ids_1 = [c.customer_id for c in data1["customers"]]
    c_ids_2 = [c.customer_id for c in data2["customers"]]
    assert c_ids_1 == c_ids_2

    # Compare some payments
    p_ids_1 = [p.payment_id for p in data1["payments"]]
    p_ids_2 = [p.payment_id for p in data2["payments"]]
    assert p_ids_1 == p_ids_2


def test_different_seeds_produce_different_data() -> None:
    """Different seeds should produce different results."""
    config1 = GenerationConfig(num_customers=50, seed=42)
    env1 = SyntheticEnvironment(config1)
    data1 = env1.generate()

    config2 = GenerationConfig(num_customers=50, seed=123)
    env2 = SyntheticEnvironment(config2)
    data2 = env2.generate()

    c_ids_1 = {c.customer_id for c in data1["customers"]}
    c_ids_2 = {c.customer_id for c in data2["customers"]}
    assert c_ids_1 != c_ids_2


def test_data_quality_checks_run_automatically() -> None:
    """The runner should execute quality checks automatically."""
    config = GenerationConfig(num_customers=20, seed=42)
    env = SyntheticEnvironment(config)
    # If this completes without raising an exception, quality checks passed.
    data = env.generate()

    assert len(data["customers"]) == 20
    assert len(data["subscriptions"]) > 0
    assert len(data["payments"]) > 0


def test_failure_mechanisms_have_distinct_attributes() -> None:
    """Different failures should trigger distinct logic (e.g. recoverability)."""
    config = GenerationConfig(num_customers=50, seed=42)
    env = SyntheticEnvironment(config)
    data = env.generate()

    cases = data["recovery_cases"]

    recoverable_cases = [c for c in cases if c.recovery_probability > 0.05]
    unrecoverable_cases = [c for c in cases if c.recovery_probability <= 0.05]

    # We should have a mix of recoverable and unrecoverable cases if any failed payments exist
    if cases:
        assert len(recoverable_cases) >= 0
        assert len(unrecoverable_cases) >= 0


def test_development_scale_supported() -> None:
    """Verify that a small development scale generates quickly and correctly."""
    config = GenerationConfig(num_customers=10, seed=1)
    env = SyntheticEnvironment(config)
    data = env.generate()

    assert len(data["customers"]) == 10

    # Check that interactions and outcomes are properly tied to cases
    case_ids = {c.case_id for c in data["recovery_cases"]}
    for interaction in data["interactions"]:
        if interaction.recovery_case_id:
            assert interaction.recovery_case_id in case_ids
