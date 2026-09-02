# REVIVE Policy and Guardrails

## 1. Purpose

This document defines deterministic safety constraints between recommendation and execution.

The agent and LLM cannot override these rules.

See [AGENT_SPEC.md](./AGENT_SPEC.md).

## 2. Default-Deny Principle

If a critical policy dependency is unavailable or a required state is ambiguous:

```text
Financial action -> DENY
Communication action -> DENY unless approved deterministic fallback
Human escalation -> ALLOW
```

## 3. Retry Limits

Default:

```text
Maximum payment retries per payment: 2
Minimum retry cooldown: 12 hours
Maximum recovery window: 14 days
```

Retry is allowed only when:

- payment remains unresolved
- retry count is below limit
- cooldown has elapsed
- cause is retry-compatible
- case is active
- action is permitted
- expected net recovery meets configured threshold

## 4. Communication Limits

Default:

```text
Maximum outbound contacts per case: 3
Minimum communication cooldown: 24 hours
```

If communication opt-out is active, all automated communication is blocked.

## 5. Customer Opt-Out

When `communication_opt_out = true`:

```text
SMS -> BLOCK
EMAIL -> BLOCK
WHATSAPP -> BLOCK
VOICE -> BLOCK
```

Internal payment-state checks and human escalation remain possible.

## 6. Stop Conditions

Stop immediately when:

1. Payment succeeds.
2. Invoice is paid.
3. Customer asks to stop communication.
4. Retry limit is reached.
5. Contact limit is reached.
6. Recovery window expires.
7. Customer disputes the transaction.
8. No permitted candidate action remains.
9. All actions have non-positive expected net recovery.
10. Human escalation is required.

Persist `stop_reason`.

## 7. High-Value Escalation

Default autonomous threshold:

```text
₹1,00,000
```

Cases above the threshold require human approval for financial actions.

Threshold is configurable.

## 8. Confidence Policy

Default:

```text
High   >= 0.85
Medium 0.60–0.8499
Low    < 0.60
```

High-confidence actions may be autonomous if all other policy checks pass.

Medium-confidence actions may execute only for configured low-risk action classes.

Low-confidence decisions require escalation or stop.

## 9. Candidate Eligibility

### Temporary issuer decline

```text
RETRY_NOW
RETRY_LATER
REMINDER
```

### Insufficient funds

```text
RETRY_LATER
REMINDER
```

### Expired card

```text
PAYMENT_METHOD_UPDATE
REMINDER
```

### Gateway failure

```text
DEFER_RETRY
ALTERNATE_GATEWAY
```

### Checkout abandonment

```text
PAYMENT_LINK
REMINDER
```

### Overdue invoice

```text
REMINDER
PROMISE_TO_PAY
FINANCE_ESCALATION
```

## 10. Intervention Budget

Default daily simulation budgets:

```text
SMS: 2,000
WhatsApp: 1,000
Voice: 100
Finance escalations: 50
```

When exhausted, that action is blocked and alternative actions are evaluated.

## 11. Simulated Intervention Costs

```text
RETRY_NOW = ₹2
RETRY_LATER = ₹2
SMS = ₹0.30
EMAIL = ₹0.05
WHATSAPP = ₹0.50
VOICE_CALL = ₹12
FINANCE_ESCALATION = ₹100
PAYMENT_METHOD_UPDATE = ₹0.50
```

These are synthetic simulation assumptions only.

## 12. Minimum Expected Net Recovery

Default:

```text
₹50
```

Actions below this threshold should not execute autonomously unless explicitly configured as strategic communication.

## 13. Idempotency

Every mutation requires a unique idempotency key.

Recommended:

```text
{case_id}:{action_type}:{attempt_number}
```

Duplicate requests return the existing action/result.

## 14. Already-Paid Protection

Before every retry or communication action:

1. Refresh payment/invoice status.
2. If paid, stop the case.
3. Cancel pending actions.
4. Record `ALREADY_PAID_STOP`.

## 15. Disputes

If a customer indicates a dispute:

```text
Automated recovery -> STOP
Human review -> REQUIRED
```

## 16. Promise-to-Pay

When a valid promise is detected:

1. Record promised date.
2. Avoid redundant immediate contact.
3. Schedule verification.
4. Re-check authoritative payment status.
5. Stop if payment occurs.

## 17. Tool Failure

### Timeout

Do not assume failure. Re-query state.

### Explicit failure

Record outcome and determine whether another action remains valid.

### Unknown state

Escalate.

## 18. Model Failure

If recovery model is unavailable:

- Do not invent probabilities.
- Use approved deterministic fallback only where configured.
- Escalate high-value cases.

If risk model is unavailable:

- Process only pre-approved deterministic cases.
- Otherwise escalate.

## 19. Policy Versioning

Every intervention stores:

```text
policy_version
configuration_hash
effective_timestamp
```

## 20. Audit Requirement

Every policy evaluation records:

```text
case_id
action
timestamp
policy_version
decision
reason_codes
amount
confidence
retry_count
contact_count
relevant thresholds
```

## 21. Safety Principle

When uncertainty is material:

```text
STOP
or
ESCALATE
```

Never use an LLM recommendation to bypass a deterministic policy.
