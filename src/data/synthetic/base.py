"""Base generator providing reproducible random state."""

import random
from typing import Any


class BaseGenerator:
    """Base class for all synthetic generators, enforcing a fixed random state."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize the generator with a deterministic seed."""
        self.seed = seed
        self.py_rng = random.Random(seed)

    def select_weighted(self, choices: list[Any], weights: list[Any]) -> Any:
        """Select an item from choices based on provided weights."""
        return self.py_rng.choices(choices, weights=weights, k=1)[0]
