"""Guardrails engine implementing deterministic safety rules."""

import uuid
from datetime import UTC, datetime

from src.database.models import Customer, Interaction, Intervention, RecoveryCase
from src.decision.models import DecisionResult
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.policy.config import GuardrailConfig
from src.policy.models import PolicyDecisionStatus, PolicyEvaluationResult


class GuardrailsEngine:
    """Evaluates proposed actions against mandatory business and safety rules."""

    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()

    def evaluate(
        self,
        decision: DecisionResult,
        case: RecoveryCase,
        customer: Customer,
        interventions: list[Intervention],
        interactions: list[Interaction],
        current_time: datetime | None = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluate an action.
        MUST fail safe (DENY) if evaluation is impossible.
        """

        def _ensure_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt

        now = _ensure_utc(current_time or datetime.now(UTC))
        case_created_at = _ensure_utc(case.created_at) if case.created_at else now

        action_type = decision.selected_action
        case_id = case.case_id

        evaluated: list[str] = []

        # 0. Safety / Fail-Safe checks
        if not action_type or not case_id:
            safe_action = action_type if action_type else "UNKNOWN"
            return self._deny(
                case_id,
                safe_action,
                "Missing mandatory data for evaluation",
                evaluated,
                ["fail_safe"],
            )

        injector = get_fault_injector()
        
        # 1. Already-paid / Already-recovered (Stop Rule)
        evaluated.append("already_resolved")
        is_already_paid = case.status in ("RECOVERED", "CLOSED", "CANCELLED") or injector.should_inject(FaultType.ALREADY_PAID, str(case_id))
        
        if is_already_paid:
            if action_type == "NO_ACTION":
                return self._no_action(case_id, "Case is already resolved.")
            return self._deny(
                case_id, action_type, "Case is already resolved.", evaluated, ["already_resolved"]
            )

        # 2. Customer Opt-Out
        evaluated.append("customer_opt_out")
        is_communication = "REMINDER" in action_type or action_type in (
            "EMAIL",
            "SMS",
            "WHATSAPP",
            "VOICE",
        )

        injector = get_fault_injector()
        is_opted_out = customer.communication_opt_out or injector.should_inject(
            FaultType.CUSTOMER_OPT_OUT, str(case_id)
        )

        if is_opted_out and is_communication:
            return self._deny(
                case_id,
                action_type,
                "Customer has opted out of communication.",
                evaluated,
                ["customer_opt_out"],
            )

        # 3. Recovery Window Expiration
        evaluated.append("recovery_window")
        window_days = (now - case_created_at).days
        if window_days > self.config.max_recovery_window_days:
            if action_type == "NO_ACTION":
                return self._no_action(case_id, "Recovery window expired.")
            return self._deny(
                case_id,
                action_type,
                f"Recovery window expired ({window_days} days).",
                evaluated,
                ["recovery_window"],
            )

        # Prevent leakage: only consider historical events strictly before `now`
        past_interventions = [i for i in interventions if _ensure_utc(i.created_at) < now]
        [i for i in interactions if _ensure_utc(i.created_at) < now]

        # 4. Retry and Contact Limits
        evaluated.append("retry_limit")
        evaluated.append("contact_limit")

        # Count retries (financial interventions)
        retry_interventions = [
            i for i in past_interventions if "RETRY" in i.action_type and i.status != "CANCELLED"
        ]
        if "RETRY" in action_type and len(retry_interventions) >= self.config.max_payment_retries:
            return self._deny(
                case_id,
                action_type,
                f"Max retries ({self.config.max_payment_retries}) reached.",
                evaluated,
                ["retry_limit"],
            )

        # Count contacts (communication interventions)
        contact_interventions = [
            i
            for i in past_interventions
            if "REMINDER" in i.action_type or i.action_type in ("EMAIL", "SMS", "WHATSAPP", "VOICE")
        ]
        if is_communication and len(contact_interventions) >= self.config.max_customer_contacts:
            return self._deny(
                case_id,
                action_type,
                f"Max contacts ({self.config.max_customer_contacts}) reached.",
                evaluated,
                ["contact_limit"],
            )

        # 5. Cooldowns
        evaluated.append("cooldown")
        if "RETRY" in action_type and retry_interventions:
            last_retry = max(_ensure_utc(i.created_at) for i in retry_interventions)
            hours_since_retry = (now - last_retry).total_seconds() / 3600.0
            if hours_since_retry < self.config.min_retry_cooldown_hours:
                return self._deny(
                    case_id,
                    action_type,
                    f"Retry cooldown active ({hours_since_retry:.1f}h elapsed).",
                    evaluated,
                    ["cooldown"],
                )

        if is_communication and contact_interventions:
            last_contact = max(_ensure_utc(i.created_at) for i in contact_interventions)
            hours_since_contact = (now - last_contact).total_seconds() / 3600.0
            if hours_since_contact < self.config.min_contact_cooldown_hours:
                return self._deny(
                    case_id,
                    action_type,
                    f"Contact cooldown active ({hours_since_contact:.1f}h elapsed).",
                    evaluated,
                    ["cooldown"],
                )

        # 6. High-Value Escalation
        evaluated.append("high_value_escalation")
        if case.amount_at_risk >= self.config.high_value_threshold and action_type not in (
            "NO_ACTION",
            "FINANCE_ESCALATION",
        ):
            return PolicyEvaluationResult(
                case_id=case_id,
                decision=PolicyDecisionStatus.ESCALATE,
                action_type=action_type,
                reason=f"High-value case (Amount: {case.amount_at_risk}) requires manual escalation.",
                guardrails_evaluated=evaluated,
                violated_guardrails=["high_value_escalation"],
            )

        # 7. Economic Minimum Threshold
        evaluated.append("economic_threshold")
        if (
            action_type != "NO_ACTION"
            and decision.expected_net_recovery < self.config.min_expected_net_recovery
        ):
            return self._deny(
                case_id,
                action_type,
                f"Expected net recovery ({decision.expected_net_recovery}) is below minimum threshold ({self.config.min_expected_net_recovery}).",
                evaluated,
                ["economic_threshold"],
            )

        # 8. NO_ACTION explicitly allowed if chosen by engine
        if action_type == "NO_ACTION":
            return self._no_action(case_id, "Engine requested NO_ACTION.")

        # 9. ALLOW
        return PolicyEvaluationResult(
            case_id=case_id,
            decision=PolicyDecisionStatus.ALLOW,
            action_type=action_type,
            reason="All guardrails passed.",
            guardrails_evaluated=evaluated,
            violated_guardrails=[],
        )

    def _deny(
        self,
        case_id: uuid.UUID,
        action_type: str,
        reason: str,
        evaluated: list[str],
        violated: list[str],
    ) -> PolicyEvaluationResult:
        return PolicyEvaluationResult(
            case_id=case_id,
            decision=PolicyDecisionStatus.DENY,
            action_type=action_type,
            reason=reason,
            guardrails_evaluated=evaluated,
            violated_guardrails=violated,
        )

    def _no_action(self, case_id: uuid.UUID, reason: str) -> PolicyEvaluationResult:
        return PolicyEvaluationResult(
            case_id=case_id,
            decision=PolicyDecisionStatus.NO_ACTION,
            action_type="NO_ACTION",
            reason=reason,
            guardrails_evaluated=[],
            violated_guardrails=[],
        )
