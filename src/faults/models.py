"""Typed fault representations for Milestone 13."""

from enum import Enum


class FaultType(str, Enum):
    """Deterministic fault types that can be injected into the system."""

    GATEWAY_OUTAGE = "GATEWAY_OUTAGE"
    API_TIMEOUT = "API_TIMEOUT"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    ALREADY_PAID = "ALREADY_PAID"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    CUSTOMER_OPT_OUT = "CUSTOMER_OPT_OUT"


class SimulatedFaultError(Exception):
    """Exception raised when a simulated fault interrupts the normal flow."""

    def __init__(self, fault_type: FaultType, message: str):
        super().__init__(f"[{fault_type.value}] {message}")
        self.fault_type = fault_type
        self.message = message
