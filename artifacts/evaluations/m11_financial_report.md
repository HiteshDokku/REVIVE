# REVIVE — Milestone 11 Financial Evaluation Report

## Executive Summary

This report presents the realized financial performance of the REVIVE revenue-recovery system compared to three baseline strategies. All financial outcomes are determined by the independent M9 InterventionSimulator, **not** by the propensity model's predicted probabilities.

## Methodology

- **Financial authority**: `InterventionSimulator.simulate()` (M9)
- **Cost authority**: M9 execution costs from POLICY.md
- **Temporal ordering**: Action selection → Guardrails → Simulator → Outcome
- **Leakage protection**: No outcome information available during action selection
- **Seeds**: [42, 43, 44, 45, 46]
- **Evaluation population**: All recovery cases per seed

## Population

- Seed 42: 1122 cases, Revenue at risk: ₹12759330.87
- Seed 43: 1171 cases, Revenue at risk: ₹9727117.53
- Seed 44: 1102 cases, Revenue at risk: ₹9357226.10
- Seed 45: 1029 cases, Revenue at risk: ₹10078143.53
- Seed 46: 1017 cases, Revenue at risk: ₹14325202.38

## Strategy Comparison (Mean Across Seeds)

| Strategy | Cases | Recovery Rate | Amount Recovered | Cost | Net Recovery | Net/Case |
|---|---:|---:|---:|---:|---:|---:|
| NO_ACTION | 1088 | 0.00% | ₹0.00 | ₹0.00 | ₹0.00 | ₹0.00 |
| ALWAYS_RETRY | 1088 | 28.59% | ₹3193570.28 | ₹2176.40 | ₹3191393.88 | ₹2944.33 |
| GENERIC_REMINDER | 1088 | 23.52% | ₹2656597.80 | ₹54.41 | ₹2656543.39 | ₹2479.58 |
| REVIVE | 1088 | 47.54% | ₹5321392.81 | ₹815.41 | ₹5320577.40 | ₹4926.56 |

## REVIVE vs Baselines (Mean Across Seeds)

| Baseline | Net Δ | Net Lift % | Recovery Rate Δ | Cost Δ | Gross Recovery Δ |
|---|---:|---:|---:|---:|---:|
| NO_ACTION | ₹5320577.40 | N/A | 47.54% | ₹815.41 | ₹5321392.81 |
| ALWAYS_RETRY | ₹2129183.52 | 67.16% | 18.95% | ₹-1360.99 | ₹2127822.53 |
| GENERIC_REMINDER | ₹2664034.01 | 108.12% | 24.02% | ₹761.00 | ₹2664795.01 |

## Safety Metrics (REVIVE, Aggregated)

- Guardrail ALLOW: 5441
- Guardrail DENY: 0
- Guardrail ESCALATE: 0
- Guardrail NO_ACTION: 0
- Economic threshold denials: 0
- High-value escalations: 0
- **Policy violations: 0**

## Model Metrics (From M6 Training Artifacts)

- M6_ROC_AUC: 0.8647056794631691
- M6_PR_AUC: 0.6182289913158223
- M6_Brier: 0.10743176193699895
- M6_LogLoss: 0.33612857858946377
- M6_F1: 0.5559914407988588
- M6_Accuracy: 0.8304623136106761

*These are model-quality metrics from the M6 training evaluation,*
*NOT realized financial metrics. They are included for completeness.*

## Multi-Seed Stability

### Total Net Recovery by Seed

| Seed | NO_ACTION | ALWAYS_RETRY | GENERIC_REMINDER | REVIVE |
|---:|---:|---:|---:|---:|
| 42 | ₹0.00 | ₹3594478.04 | ₹2605947.31 | ₹5906581.80 |
| 43 | ₹0.00 | ₹3039734.29 | ₹1673908.78 | ₹4408370.25 |
| 44 | ₹0.00 | ₹2821352.86 | ₹2277537.51 | ₹4654193.01 |
| 45 | ₹0.00 | ₹2684866.54 | ₹2946247.30 | ₹5128735.67 |
| 46 | ₹0.00 | ₹3816537.68 | ₹3779076.05 | ₹6505006.27 |

### Aggregation (Net Recovery)

| Strategy | Mean | Std | Min | Max |
|---|---:|---:|---:|---:|
| NO_ACTION | ₹0.00 | ₹0.00 | ₹0.00 | ₹0.00 |
| ALWAYS_RETRY | ₹3191393.88 | ₹492387.69 | ₹2684866.54 | ₹3816537.68 |
| GENERIC_REMINDER | ₹2656543.39 | ₹783547.08 | ₹1673908.78 | ₹3779076.05 |
| REVIVE | ₹5320577.40 | ₹874537.91 | ₹4408370.25 | ₹6505006.27 |

## Integrity / Leakage Audit

- ✅ Action selection precedes simulation execution
- ✅ Outcomes (`amount_recovered`, `status_after`) unavailable during selection
- ✅ InterventionSimulator is the sole financial authority
- ✅ No target leakage (cases presented as OPEN, predictions stripped)
- ✅ No future-information leakage (no past interventions/interactions provided)
- ✅ All strategies evaluate the same population per seed
- ✅ Per-case deterministic seeds ensure fair random draws

## Limitations

1. All results are based on a **synthetic simulator** with known causal assumptions.
2. The simulator's causal matrix is fixed; real-world effectiveness would differ.
3. Each case receives exactly one intervention attempt (no multi-step recovery).
4. Cost discrepancy: M7 decision costs differ from M9 execution costs used here.
5. REVIVE's guardrails may block economically marginal actions that baselines execute.
6. Results should not be directly extrapolated to real-world financial performance.

## Reproducibility Metadata

- **evaluation_timestamp**: 2026-08-30T07:15:46.954914+00:00
- **seeds**: [42, 43, 44, 45, 46]
- **num_customers_per_seed**: 500
- **num_months**: 6
- **cost_source**: M9 execution costs (POLICY.md)
- **cost_table**: {'NO_ACTION': '0.00', 'RETRY_LATER': '2.00', 'RETRY_NOW': '2.00', 'EMAIL_REMINDER': '0.05', 'SMS_REMINDER': '0.30', 'WHATSAPP_REMINDER': '0.50', 'VOICE_CALL': '12.00', 'FINANCE_ESCALATION': '100.00', 'UPDATE_PAYMENT_METHOD': '0.50'}
- **strategies**: ['NO_ACTION', 'ALWAYS_RETRY', 'GENERIC_REMINDER', 'REVIVE']
- **simulator**: src.simulator.engine.InterventionSimulator
- **evaluation_engine**: src.evaluation.engine.EvaluationEngine
- **python_version**: 3.14.6
- **platform**: Windows-11-10.0.26200-SP0
- **duration_seconds**: 264.548943
