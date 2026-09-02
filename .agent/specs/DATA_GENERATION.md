# REVIVE Synthetic Data Generation Specification

## 1. Purpose

Create a controlled but realistic synthetic merchant environment suitable for model training, simulation, evaluation, and demonstrations.

Synthetic data must preserve relationships among customers, subscriptions, payments, invoices, interactions, interventions, and outcomes.

See [SCHEMA.md](./SCHEMA.md) and [ML_SPEC.md](./ML_SPEC.md).

## 2. Reproducibility

Every generator accepts `seed` and produces deterministic results for identical configuration and seed.

Default seed: `42`.

## 3. Default Scale

```text
Customers: 5,000
Months: 6
Subscriptions: 7,500
Payments: 120,000
Invoices: 15,000
Interactions: 20,000
Intervention outcomes: 30,000+
```

The implementation must allow smaller development datasets and larger evaluation datasets.

## 4. Customer Archetypes

Default weighted mix:

```text
RELIABLE_CONSUMER       35%
OCCASIONALLY_LATE       25%
HIGH_RISK_CONSUMER      15%
PREMIUM_CUSTOMER        10%
SMALL_BUSINESS           8%
MID_MARKET_BUSINESS      5%
NEW_CUSTOMER             2%
```

Weights must be configurable.

## 5. Customer Behavior

Each customer receives latent behavioral properties that influence generated outcomes:

- payment reliability
- delay tendency
- preferred communication channel
- language preference
- customer value
- response tendency
- likelihood of promising payment

Use beta distributions for bounded reliability and log-normal-like distributions for skewed monetary values.

## 6. Subscription Generation

Each applicable customer receives 0–4 subscriptions.

Suggested billing bands:

```text
Basic       ₹199–₹999
Standard    ₹1,000–₹4,999
Premium     ₹5,000–₹25,000
Business    ₹25,000–₹2,00,000
```

Ranges should be generated from distributions rather than uniform random sampling across the full band.

## 7. Payment Generation

For every billing event:

1. Determine customer state.
2. Apply temporal effects.
3. Apply payment-method effects.
4. Apply gateway state.
5. Determine payment success/failure.
6. If failed, select a meaningful failure mechanism.
7. Create recovery opportunity where appropriate.

## 8. Failure Distribution

Default failure mix:

```text
TEMPORARY_ISSUER_DECLINE   18%
INSUFFICIENT_FUNDS          15%
EXPIRED_CARD                10%
INVALID_PAYMENT_METHOD       7%
GATEWAY_FAILURE             10%
NETWORK_TIMEOUT              8%
CUSTOMER_ABANDONMENT        12%
DUPLICATE_PAYMENT             3%
UNKNOWN                       4%
OTHER_RECOVERABLE            13%
```

The generator must ensure failure mechanisms have different recovery characteristics.

## 9. Failure Semantics

### Temporary issuer decline

Delayed retry should outperform immediate retry.

### Insufficient funds

Immediate retry is less effective than a delay-aware retry.

### Expired card

Retrying the same payment method should be ineffective; payment-method update should be preferred.

### Gateway failure

Failures should correlate by gateway and time window. Retrying during an outage should have low expected value.

### Checkout abandonment

Reminder or payment-link interventions should have value; payment retry without a completed payment attempt should not be a valid action.

### Overdue invoice

Reminder, promise-to-pay, and finance escalation should become candidate actions depending on age/value.

## 10. Temporal Effects

Implement configurable effects for:

- day of month
- weekday/weekend
- monthly billing cycles
- salary-cycle-like payment patterns
- holiday-like behavior changes

These are synthetic assumptions and must not be presented as real-world statistics.

## 11. Gateway Environment

Default gateways:

```text
gateway_a
gateway_b
gateway_c
```

Each gateway has configurable:

- base success rate
- latency
- timeout probability
- failure distribution

## 12. Gateway Degradation

A degradation scenario should increase gateway-specific failure probability over a bounded time window.

Example configuration:

```yaml
gateway: gateway_a
severity: 0.8
duration_minutes: 60
```

The resulting events should be correlated enough for anomaly detection to identify a cluster.

## 13. Checkout Funnel

Generate:

```text
SESSION_STARTED
PRODUCT_VIEWED
CHECKOUT_STARTED
PAYMENT_FORM_OPENED
PAYMENT_ATTEMPTED
PURCHASE_COMPLETED
```

A session with a non-completed terminal state after reaching payment stage can generate recoverable checkout revenue.

## 14. Invoice Generation

Business customers receive invoices with realistic skewed amounts.

Suggested bands:

```text
Small business  ₹5,000–₹1,00,000
Mid-market      ₹50,000–₹10,00,000
```

Overdue behavior depends on customer archetype and historical delay.

## 15. Interaction Generation

Historical communications are generated only when a recovery case or simulated customer engagement exists.

Channels:

```text
EMAIL
SMS
WHATSAPP
VOICE
ACCOUNT_MANAGER
```

Possible responses:

```text
NO_RESPONSE
PROMISE_TO_PAY
ALREADY_PAID
STOP_CONTACTING
PAYMENT_PROBLEM
CONFUSED
DISPUTE
QUESTION
```

## 16. Hinglish Examples

A controlled subset of text responses should contain Hinglish, such as:

```text
Kal shaam payment kar dunga.
Aaj funds nahi hai, weekend pe karunga.
Payment already kar diya hai.
Please mujhe message mat karna.
```

The simulator must retain ground-truth intent separately from generated text so the language-model extractor can be evaluated.

## 17. Intervention Outcome Simulation

For each historical intervention, compute outcome probability using state features:

```text
customer reliability
failure type
action type
amount
retry count
elapsed time
channel
communication history
gateway state
payment history
```

Then sample the actual result.

## 18. Counterfactual Action Records

Where possible, retain action-level outcome observations so one case can have several candidate action records.

Required training shape:

```text
case_features
candidate_action
action_cost
outcome
amount_recovered
```

This supports later contextual-bandit/RL experiments.

## 19. Edge Cases

The dataset must contain:

- duplicate events
- already-paid cases
- opted-out customers
- maximum retry reached
- expired recovery windows
- API timeouts
- unknown failure causes
- missing optional attributes
- gateway outage
- multiple subscriptions sharing payment method
- simultaneous failures for a customer
- conflicting customer responses
- high-value escalations

## 20. Labels

### Recoverable risk

Set `recoverable_risk = 1` when the event represents revenue that would otherwise remain unpaid/lost and at least one reasonable intervention can cause recovery in the simulated environment.

### Root cause

Use the simulator's generated ground-truth failure mechanism.

### Recovery

Set `recovered = 1` when the simulated case reaches successful payment/recovery within the configured recovery window.

## 21. Data Quality Checks

Fail generation when:

- duplicate primary keys exist
- foreign keys are broken
- negative money values exist
- recovered amount exceeds amount at risk
- dates are logically inconsistent
- promised dates precede response dates
- retry counts are negative
- outcomes exist without interventions

## 22. Data Split Support

The generator must create temporally ordered data:

```text
Months 1–4 -> Train
Month 5     -> Validation
Month 6     -> Test
```

Do not use random shuffling as the only evaluation protocol.
