"""Deterministic root-cause mapping rules."""

from typing import ClassVar


class DeterministicRootCauseMapper:
    """Resolves root causes deterministically for unambiguous provider codes/reasons."""

    KNOWN_PROVIDER_CODES: ClassVar[dict[str, str]] = {
        "ERR_EXPIRED_101": "EXPIRED_CARD",
        "ERR_NSF_201": "INSUFFICIENT_FUNDS",
        "ERR_INV_METHOD_301": "INVALID_PAYMENT_METHOD",
        "ERR_GW_FAIL_401": "GATEWAY_FAILURE",
        "ERR_NET_TIMEOUT_501": "NETWORK_TIMEOUT",
        "ERR_DECLINE_601": "TEMPORARY_ISSUER_DECLINE",
        "ERR_ABANDON_701": "CUSTOMER_ABANDONMENT",
        "ERR_DUP_801": "DUPLICATE_PAYMENT",
        "ERR_INV_OVERDUE_901": "OVERDUE_INVOICE",
        # Legacy/test explicit codes
        "ERR_EXPIRED": "EXPIRED_CARD",
        "ERR_INSUFFICIENT": "INSUFFICIENT_FUNDS",
        "ERR_INVALID_METHOD": "INVALID_PAYMENT_METHOD",
        "ERR_DUPLICATE": "DUPLICATE_PAYMENT",
        "ERR_TIMEOUT": "NETWORK_TIMEOUT",
        "ERR_GATEWAY_DOWN": "GATEWAY_FAILURE",
    }

    def map_root_cause(
        self,
        source_type: str | None = None,
        failure_code: str | None = None,
        failure_reason: str | None = None,
    ) -> tuple[str, float, bool] | None:
        """
        Attempt to deterministically map inputs to a root cause.

        Returns (root_cause, confidence, is_deterministic) if mapped, else None.
        Confidence is always 1.0 for deterministic mappings.
        """
        # 1. Check source_type (e.g., invoices are always OVERDUE_INVOICE)
        if source_type == "invoice":
            return ("OVERDUE_INVOICE", 1.0, True)

        # 2. Check explicit provider failure codes
        if failure_code and failure_code in self.KNOWN_PROVIDER_CODES:
            return (self.KNOWN_PROVIDER_CODES[failure_code], 1.0, True)

        # Generic / ambiguous failure_code (ERR_GENERIC_9xx) or unknown provider response -> Return None to trigger ML Fallback
        return None
