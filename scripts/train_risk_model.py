import argparse
import hashlib
import json
import os
import random
import typing
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment
from src.features.risk_features import RiskFeatureExtractor


def revenue_recall(y_true: Any, y_pred: Any, amounts: Any) -> float:
    """Calculates Revenue Recall: Recoverable revenue correctly identified / Total truly recoverable revenue."""
    truly_recoverable_idx = y_true == 1
    total_truly_recoverable = amounts[truly_recoverable_idx].sum()
    if total_truly_recoverable == 0:
        return 0.0
    correctly_identified = amounts[truly_recoverable_idx & (y_pred == 1)].sum()
    return float(correctly_identified / total_truly_recoverable)


def get_temporal_split(df: pd.DataFrame, config: Any) -> tuple[pd.Series, pd.Series, pd.Series]:
    start_date = datetime.fromisoformat(config.start_date.replace("Z", "+00:00"))

    df["created_at_dt"] = pd.to_datetime(df["created_at"])
    df["month_diff"] = (df["created_at_dt"].dt.year - start_date.year) * 12 + (
        df["created_at_dt"].dt.month - start_date.month
    )

    # Months 1-4 correspond to month_diff 0, 1, 2, 3
    # Month 5 corresponds to month_diff 4
    # Month 6 corresponds to month_diff 5

    train_idx = df["month_diff"] <= 3
    val_idx = df["month_diff"] == 4
    test_idx = df["month_diff"] == 5

    return train_idx, val_idx, test_idx


def create_pipeline(model: Any) -> Any:
    numeric_features = [
        "amount",
        "hour",
        "weekday",
        "day_of_month",
        "customer_age_days",
        "active_subscriptions",
        "lifetime_value",
        "payment_reliability_score",
        "avg_payment_delay_days",
        "historical_success_rate",
        "failure_count",
        "failures_last_30d",
        "prior_recovery_rate",
        "current_retry_count",
        "intervention_count",
    ]
    categorical_features = ["payment_method", "gateway", "failure_code", "failure_reason"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", model)])


def evaluate_model(
    name: str, model: Any, x_test: Any, y_test: Any, amounts_test: Any
) -> dict[str, Any]:
    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]

    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    pr_auc = average_precision_score(y_test, y_prob)
    roc_auc = roc_auc_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    # Calibration error (Expected Calibration Error)
    prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=10)
    ece = np.mean(np.abs(prob_true - prob_pred))

    rev_recall = revenue_recall(y_test, y_pred, amounts_test)

    return {
        "model_type": name,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc_auc),
        "brier_score": float(brier),
        "calibration_error": float(ece),
        "revenue_recall": float(rev_recall),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Risk Model")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"Starting Risk Model Training (Seed: {args.seed})")

    # Enforce strict reproducibility
    random.seed(args.seed)
    np.random.seed(args.seed)

    # 1. Data Generation
    print("Generating synthetic data...")
    config = GenerationConfig(seed=args.seed)
    env = SyntheticEnvironment(config)
    data = env.generate()

    # 2. Feature Extraction
    print("Extracting features (Zero-Leakage Guarantee)...")
    extractor = RiskFeatureExtractor(
        customers=data["customers"], payments=data["payments"], cases=data["recovery_cases"]
    )
    df = extractor.extract_all(data["recovery_cases"])

    # 3. Temporal Split
    print("Applying strict temporal split (Months 1-4 Train, 5 Val, 6 Test)...")
    train_idx, val_idx, test_idx = get_temporal_split(df, config)

    df_train = df[train_idx]
    df_val = df[val_idx]
    df_test = df[test_idx]

    print(f"Train size: {len(df_train)}, Val size: {len(df_val)}, Test size: {len(df_test)}")

    feature_cols = [
        c
        for c in df.columns
        if c not in ("label", "case_id", "created_at", "created_at_dt", "month_diff")
    ]
    print("\nFeatures Used:")
    for c in feature_cols:
        print(f" - {c}")

    x_train = df_train[feature_cols]
    y_train = df_train["label"]

    x_test = df_test[feature_cols]
    y_test = df_test["label"]
    amounts_test = df_test["amount"]

    # 4. Model Training & Comparison
    print("\nTraining models...")
    models = {
        "Majority Baseline": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(random_state=args.seed, max_iter=1000),
        "Random Forest": RandomForestClassifier(random_state=args.seed, n_estimators=100),
        "XGBoost": XGBClassifier(
            random_state=args.seed, use_label_encoder=False, eval_metric="logloss"
        ),
    }

    results = []
    trained_pipelines = {}

    for name, model in models.items():
        print(f"  - Training {name}...")
        pipeline = create_pipeline(model)
        pipeline.fit(x_train, y_train)
        trained_pipelines[name] = pipeline

        metrics = evaluate_model(name, pipeline, x_test, y_test, amounts_test)
        results.append(metrics)

    print("\n--- Model Comparison on Test Set ---")
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    selected_model_name = "XGBoost"
    _ = trained_pipelines[selected_model_name]

    print(f"\nSelected Model: {selected_model_name}")

    # 6. Calibration
    print("Calibrating selected model...")
    # We will fit the calibration on the training set using cross-validation
    calibrated = CalibratedClassifierCV(
        estimator=models[
            selected_model_name
        ],  # Need the base model, not the pipeline, or we can use the pipeline
        cv=5,
        method="isotonic",
    )
    # We must wrap it in a pipeline if we use the base model, or we can just pass the pipeline!
    calibrated_pipeline = create_pipeline(calibrated)
    calibrated_pipeline.fit(x_train, y_train)

    calibrated_metrics = evaluate_model(
        f"Calibrated {selected_model_name}", calibrated_pipeline, x_test, y_test, amounts_test
    )
    print("\n--- Calibrated Model Performance on Test Set ---")
    calibrated_df = pd.DataFrame([calibrated_metrics])
    print(calibrated_df.to_string(index=False))

    # 7. Persistence
    print("\nPersisting model and metadata...")
    os.makedirs("artifacts/models", exist_ok=True)

    model_path = "artifacts/models/revenue_risk_model.joblib"
    metadata_path = "artifacts/models/revenue_risk_metadata.json"

    joblib.dump(calibrated_pipeline, model_path)

    # Generate metadata
    schema_version = "1.0.0"
    dataset_hash = hashlib.sha256(
        typing.cast("bytes", pd.util.hash_pandas_object(df_train).values)
    ).hexdigest()

    metadata = {
        "model_name": "revenue_risk",
        "model_version": "1.0.0",
        "model_type": "Calibrated XGBoost (Isotonic)",
        "training_timestamp": datetime.now(UTC).isoformat(),
        "training_dataset_hash": dataset_hash,
        "feature_schema_version": schema_version,
        "artifact_uri": f"file:///{os.path.abspath(model_path)}",
        "metrics": calibrated_metrics,
        "configuration": {"seed": args.seed, "features": feature_cols},
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved model to: {model_path}")
    print(f"Saved metadata to: {metadata_path}")
    print("\nMilestone 4 Training Pipeline Complete.")


if __name__ == "__main__":
    main()
