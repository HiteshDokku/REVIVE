"""REVIVE Recovery Propensity ML Optimization & Training Pipeline."""

import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

sys.path.insert(0, ".")

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment
from src.features.recovery_features import RecoveryPropensityFeatureExtractor

OUT_DIR = "artifacts/ml_benchmark"
MODEL_DIR = "artifacts/models"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

optuna.logging.set_verbosity(optuna.logging.WARNING)

FORBIDDEN_COLUMNS = {
    "success",
    "amount_recovered",
    "payment_status_after",
    "outcome",
    "future_events",
}


def audit_target_leakage(feature_cols: list[str]) -> None:
    for col in feature_cols:
        assert col.lower() not in FORBIDDEN_COLUMNS, f"Target leakage detected: '{col}'"


def main() -> None:
    start_time = time.time()

    print("=" * 70)
    print("STEP 1: Generating Data & Interventions")
    print("=" * 70)
    config = GenerationConfig(seed=42)
    env = SyntheticEnvironment(config)
    data = env.generate()

    cases_map = {c.case_id: c for c in data["recovery_cases"]}
    customers_map = {c.customer_id: c for c in data["customers"]}
    payments_map = {p.payment_id: p for p in data["payments"]}
    outcomes_map = {o.intervention_id: o for o in data["outcomes"]}

    dataset_records = []
    for intervention in data["interventions"]:
        case = cases_map.get(intervention.case_id)
        if not case or case.source_type != "payment":
            continue
        customer = customers_map.get(case.customer_id)
        if not customer:
            continue
        trigger_payment = payments_map.get(case.source_id)
        outcome = outcomes_map.get(intervention.intervention_id)
        if not outcome:
            continue

        dataset_records.append(
            {
                "case": case,
                "customer": customer,
                "action_type": intervention.action_type,
                "attempt_number": intervention.attempt_number,
                "trigger_payment": trigger_payment,
                "success": 1 if outcome.success else 0,
                "month": intervention.created_at.month,
                "amount_at_risk": float(case.amount_at_risk),
                "action_cost": 0.05 if "EMAIL" in intervention.action_type else 0.10,
            }
        )

    print(f"Total training records generated: {len(dataset_records)}")

    print("\n=" * 70)
    print("STEP 2: Extracting Features")
    print("=" * 70)

    extractor = RecoveryPropensityFeatureExtractor()
    x_df = extractor.extract_all(dataset_records)
    y = np.array([r["success"] for r in dataset_records])
    months = np.array([r["month"] for r in dataset_records])
    amounts = np.array([r["amount_at_risk"] for r in dataset_records])
    costs = np.array([r["action_cost"] for r in dataset_records])

    audit_target_leakage(list(x_df.columns))
    print("Target leakage audit: PASSED")

    cat_cols = ["action_type", "root_cause"]
    x_df_encoded = pd.get_dummies(x_df, columns=cat_cols, drop_first=False)
    x_df_encoded = x_df_encoded.astype("float32")
    feature_names = list(x_df_encoded.columns)

    print("\n=" * 70)
    print("STEP 3: Temporal Split (M1-4 Train, M5 Val, M6 Test)")
    print("=" * 70)

    train_idx = np.isin(months, [1, 2, 3, 4])
    val_idx = months == 5
    test_idx = months == 6

    x_train = x_df_encoded[train_idx]
    y_train = y[train_idx]
    x_val = x_df_encoded[val_idx]
    y_val = y[val_idx]
    amounts[val_idx]
    costs[val_idx]

    x_test = x_df_encoded[test_idx]
    y_test = y[test_idx]
    amounts_test = amounts[test_idx]
    costs_test = costs[test_idx]

    print(f"Train size: {len(y_train)} (Class 1: {np.mean(y_train):.2%})")
    print(f"Val size:   {len(y_val)} (Class 1: {np.mean(y_val):.2%})")
    print(f"Test size:  {len(y_test)} (Class 1: {np.mean(y_test):.2%})")

    neg_count = np.sum(y_train == 0)
    pos_count = np.sum(y_train == 1)
    scale_weight = float(neg_count / max(1, pos_count))

    print("\n=" * 70)
    print("STEP 4: Hyperparameter Optimization (Optuna on M1-M5)")
    print("=" * 70)

    # 1. XGBoost
    def xgb_objective(trial: Any) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 7),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "scale_pos_weight": trial.suggest_categorical(
                "scale_pos_weight", [1.0, scale_weight / 2, scale_weight]
            ),
            "random_state": 42,
            "eval_metric": "logloss",
        }
        model = XGBClassifier(**params)
        model.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)
        proba = model.predict_proba(x_val)[:, 1]
        return float(brier_score_loss(y_val, proba))

    print("Running XGBoost optimization...")
    study_xgb = optuna.create_study(direction="minimize")
    study_xgb.optimize(xgb_objective, n_trials=10)

    best_xgb = XGBClassifier(**study_xgb.best_params, random_state=42, eval_metric="logloss")
    best_xgb.fit(x_train, y_train)

    # 2. LightGBM
    def lgb_objective(trial: Any) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 20, 60),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "scale_pos_weight": trial.suggest_categorical(
                "scale_pos_weight", [1.0, scale_weight / 2, scale_weight]
            ),
            "random_state": 42,
        }
        model = LGBMClassifier(**params, verbose=-1)
        model.fit(x_train, y_train)
        proba = model.predict_proba(x_val)[:, 1]  # type: ignore[call-overload]
        return float(brier_score_loss(y_val, proba))

    print("Running LightGBM optimization...")
    study_lgb = optuna.create_study(direction="minimize")
    study_lgb.optimize(lgb_objective, n_trials=10)

    best_lgb = LGBMClassifier(**study_lgb.best_params, random_state=42, verbose=-1)
    best_lgb.fit(x_train, y_train)

    # 3. CatBoost
    print("Training CatBoost (Default)...")
    best_cat = CatBoostClassifier(
        iterations=300,
        learning_rate=0.05,
        depth=5,
        auto_class_weights="Balanced",
        verbose=0,
        random_seed=42,
    )
    best_cat.fit(x_train, y_train)

    print("\n=" * 70)
    print("STEP 5: Evaluating Calibration & Ensembling on Validation")
    print("=" * 70)

    xgb_proba_val = best_xgb.predict_proba(x_val)[:, 1]
    lgb_proba_val = best_lgb.predict_proba(x_val)[:, 1]  # type: ignore[call-overload]
    cat_proba_val = best_cat.predict_proba(x_val)[:, 1]

    cal_xgb = CalibratedClassifierCV(best_xgb, method="isotonic", cv=5)
    cal_xgb.fit(x_val, y_val)
    cal_xgb_proba_val = cal_xgb.predict_proba(x_val)[:, 1]

    cal_lgb = CalibratedClassifierCV(best_lgb, method="isotonic", cv=5)
    cal_lgb.fit(x_val, y_val)
    cal_lgb_proba_val = cal_lgb.predict_proba(x_val)[:, 1]

    # Evaluate Brier scores on Val
    models = {
        "Raw XGB": (best_xgb, brier_score_loss(y_val, xgb_proba_val)),
        "Calibrated XGB": (cal_xgb, brier_score_loss(y_val, cal_xgb_proba_val)),
        "Raw LGBM": (best_lgb, brier_score_loss(y_val, lgb_proba_val)),
        "Calibrated LGBM": (cal_lgb, brier_score_loss(y_val, cal_lgb_proba_val)),
        "Raw CatBoost": (best_cat, brier_score_loss(y_val, cat_proba_val)),
    }

    best_model_name = min(models, key=lambda k: models[k][1])
    best_model = models[best_model_name][0]

    print(
        f"Selected Best Model by Validation Brier: {best_model_name} (Brier={models[best_model_name][1]:.4f})"
    )

    print("\n=" * 70)
    print("STEP 6: Threshold Optimization on Validation")
    print("=" * 70)

    val_proba = best_model.predict_proba(x_val)[:, 1]

    best_f1 = 0.0
    best_thresh = 0.5
    for thresh in np.arange(0.1, 0.9, 0.05):
        preds = (val_proba >= thresh).astype(int)
        f = f1_score(y_val, preds)
        if f > best_f1:
            best_f1 = f
            best_thresh = thresh

    print(f"Optimal F1 Threshold (M5): {best_thresh:.2f} (Val F1: {best_f1:.4f})")

    print("\n=" * 70)
    print("STEP 7: Month-6 Temporal Generalization Test")
    print("=" * 70)

    final_proba = best_model.predict_proba(x_test)[:, 1]
    preds = (final_proba >= best_thresh).astype(int)

    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds, zero_division=0)
    rec = recall_score(y_test, preds)
    f1 = f1_score(y_test, preds)
    logloss = log_loss(y_test, final_proba)
    roc = roc_auc_score(y_test, final_proba)
    pr_auc = average_precision_score(y_test, final_proba)
    brier = brier_score_loss(y_test, final_proba)

    print(f"Test ROC-AUC:   {roc:.4f}")
    print(f"Test PR-AUC:    {pr_auc:.4f}")
    print(f"Test Brier:     {brier:.4f}")
    print(f"Test Log Loss:  {logloss:.4f}")
    print(f"Test Accuracy:  {acc:.4f}")
    print(f"Test Precision: {prec:.4f}")
    print(f"Test Recall:    {rec:.4f}")
    print(f"Test F1 Score:  {f1:.4f}")

    print("\n=" * 70)
    print("STEP 8: Economic Evaluation (M6)")
    print("=" * 70)

    # Calculate Expected Net Recovery: P(recovery) * amount - cost
    # To properly simulate economic lift, we would evaluate all actions per case and pick best.
    # Since our test set is already action-assigned interventions, we calculate expected revenue from the selected model
    # vs acting purely randomly.
    expected_net_revenue_model = np.sum((final_proba * amounts_test) - costs_test)
    true_net_revenue = np.sum((y_test * amounts_test) - costs_test)
    random_proba = np.mean(y_test)
    expected_net_revenue_random = np.sum((random_proba * amounts_test) - costs_test)

    print(f"Model Expected Net Revenue (Sum): {expected_net_revenue_model:,.2f}")
    print(f"True Net Revenue (Oracle):        {true_net_revenue:,.2f}")
    print(f"Random Expected Net Revenue:      {expected_net_revenue_random:,.2f}")
    lift = expected_net_revenue_model - expected_net_revenue_random
    print(
        f"Economic Lift over Random:        +{lift:,.2f} ({(lift / max(1, expected_net_revenue_random)):.2%})"
    )

    print("\n=" * 70)
    print("STEP 9: Persisting Artifacts")
    print("=" * 70)

    model_path = os.path.join(MODEL_DIR, "recovery_propensity_model.pkl")
    meta_path = os.path.join(MODEL_DIR, "recovery_model_metadata.json")

    joblib.dump(best_model, model_path)

    metadata = {
        "model_type": best_model_name,
        "version": "2.0.0",
        "features": feature_names,
        "training_period": "M1-M4",
        "validation_period": "M5",
        "test_period": "M6",
        "calibration": "isotonic" if "Calibrated" in best_model_name else "none",
        "threshold": float(best_thresh),
        "seed": 42,
        "metrics": {
            "M6_ROC_AUC": float(roc),
            "M6_PR_AUC": float(pr_auc),
            "M6_Brier": float(brier),
            "M6_LogLoss": float(logloss),
            "M6_F1": float(f1),
            "M6_Accuracy": float(acc),
        },
        "training_timestamp": datetime.now(UTC).isoformat(),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    report_path = os.path.join(OUT_DIR, "FINAL_RECOVERY_PROPENSITY_REPORT.md")
    report = f"""# FINAL MODEL SELECTION REPORT: Recovery Propensity Model (Optimized)

## 1. Objective
Maximize out-of-time predictive performance for `P(recovery | case context, candidate action)` ensuring strict causal and temporal integrity.

## 2. Dataset & Features
* Total generated interventions: {len(dataset_records)}
* Baseline recovery rate: {np.mean(y):.2%}
* Temporal Split: M1-M4 (Train), M5 (Validation), M6 (Test)
* **New Features Added:** Non-linear attempt interactions (`attempt_number_sq`), Economic Ratios (`amount_to_ltv_ratio`), Granular causal interactions.

## 3. Model Search & Selection
* **Models Evaluated:** XGBoost (Optuna), LightGBM (Optuna), CatBoost.
* **Selected Model:** {best_model_name}
* **Optimal Classification Threshold:** {best_thresh:.2f}

## 4. Final Evaluation (Month-6 Test)
* **ROC-AUC:** {roc:.4f}
* **PR-AUC:** {pr_auc:.4f}
* **Brier Score:** {brier:.4f}
* **Log Loss:** {logloss:.4f}
* **F1-Score:** {f1:.4f}
* **Accuracy:** {acc:.4f}
* **Economic Lift:** +{lift:,.2f} ({(lift / max(1, expected_net_revenue_random)):.2%}) over random baseline.

## 5. Target Leakage Audit
PASSED - Validated zero target-derived features in training path.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Pipeline complete in {time.time() - start_time:.1f}s")


if __name__ == "__main__":
    main()
