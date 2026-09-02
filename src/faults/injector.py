"""Deterministic fault injector for Milestone 13."""

import threading
from typing import Optional

from src.faults.models import FaultType, SimulatedFaultError


class FaultInjector:
    """
    Centralized fault injector for deterministic failure recovery testing.
    Thread-safe global singleton pattern to ensure independent execution paths
    can read configured faults.
    """

    _instance: Optional["FaultInjector"] = None
    _lock = threading.Lock()
    _configured_faults: set[FaultType]
    _target_case_id: str | None

    def __new__(cls) -> "FaultInjector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._configured_faults = set()
                cls._instance._target_case_id = None
        return cls._instance

    def configure(self, fault_type: FaultType, target_case_id: str | None = None) -> None:
        """
        Configure a fault to be injected.
        If target_case_id is provided, the fault is only injected for that case.
        """
        with self._lock:
            self._configured_faults.add(fault_type)
            if target_case_id:
                self._target_case_id = str(target_case_id)

    def clear(self) -> None:
        """Reset the injector, removing all configured faults."""
        with self._lock:
            self._configured_faults.clear()
            self._target_case_id = None

    def should_inject(self, fault_type: FaultType, case_id: str | None = None) -> bool:
        """Check if a specific fault should be injected for a given context."""
        with self._lock:
            if fault_type not in self._configured_faults:
                return False
            if (
                self._target_case_id is not None
                and case_id is not None
                and self._target_case_id != str(case_id)
            ):
                return False
            return True

    def inject_if_configured(self, fault_type: FaultType, case_id: str | None = None) -> None:
        """Raise a SimulatedFaultError if the fault is configured."""
        if self.should_inject(fault_type, case_id):
            raise SimulatedFaultError(
                fault_type=fault_type, message=f"Simulated fault {fault_type.value} injected."
            )


# Global accessor
def get_fault_injector() -> FaultInjector:
    return FaultInjector()
