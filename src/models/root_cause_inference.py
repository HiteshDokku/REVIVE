"""Hybrid Inference Service for Root-Cause diagnosis.

Supports:
- Deterministic rule-based mapping for unambiguous cases
- ML ensemble fallback with top-k predictions and confidence levels
"""

import json
import os
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.models.root_cause_rules import DeterministicRootCauseMapper

# Confidence thresholds (tuned on Month 5 validation)
HIGH_CONFIDENCE_THRESHOLD = 0.35
MEDIUM_CONFIDENCE_THRESHOLD = 0.20


class RootCauseInferenceService:
    """Hybrid inference service combining deterministic rules with ML ensemble fallback."""

    def __init__(
        self,
        model_path: str = "artifacts/models/revive_root_cause_model.pkl",
        metadata_path: str = "artifacts/models/model_metadata.json",
    ) -> None:
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.deterministic_mapper = DeterministicRootCauseMapper()
        self.artifact: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}
        self._loaded = False

    def _load_ml_model(self) -> None:
        if self._loaded:
            return

        if not os.path.exists(self.model_path) or not os.path.exists(self.metadata_path):
            raise FileNotFoundError(
                f"Model artifact or metadata missing at {self.model_path} / {self.metadata_path}"
            )

        self.artifact = joblib.load(self.model_path)

        with open(self.metadata_path) as f:
            self.metadata = json.load(f)

        self._loaded = True

    def _get_confidence_status(self, confidence: float) -> str:
        """Classify prediction confidence level."""
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            return "HIGH"
        elif confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    def diagnose(
        self,
        source_type: str | None = None,
        failure_code: str | None = None,
        failure_reason: str | None = None,
        features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Diagnose the root cause of a failure.

        First attempts deterministic mapping. If ambiguous, falls back to the ML ensemble.

        Returns:
            Dict with primary_root_cause, confidence, top_predictions,
            confidence_status, and metadata.
        """
        # 1. Deterministic mapping check
        rule_result = self.deterministic_mapper.map_root_cause(
            source_type=source_type,
            failure_code=failure_code,
            failure_reason=failure_reason,
        )

        if rule_result is not None:
            root_cause, confidence, _ = rule_result
            return {
                "root_cause": root_cause,
                "confidence": float(confidence),
                "top_predictions": [
                    {"root_cause": root_cause, "probability": float(confidence)},
                ],
                "confidence_status": "HIGH",
                "model_name": "root_cause_deterministic",
                "model_version": "1.0.0",
                "is_deterministic": True,
            }

        # 2. ML Ensemble Fallback
        if features is None:
            raise ValueError(
                "Features payload required for ML fallback when deterministic mapping is ambiguous."
            )

        self._load_ml_model()

        # Check for ensemble vs legacy single-model artifact
        if "model_lr" in self.artifact:
            return self._predict_ensemble(features)
        elif "pipeline" in self.artifact:
            return self._predict_legacy(features)
        else:
            raise ValueError("Unknown model artifact format.")

    def _predict_ensemble(self, features: dict[str, Any]) -> dict[str, Any]:
        """Predict using the tuned probability ensemble."""
        df = pd.DataFrame([features])
        feature_cols = self.artifact["feature_cols"]
        classes = self.artifact["classes"]

        # Validate features
        for col in feature_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required feature: {col}")

        df = df[feature_cols]

        prep_lin = self.artifact["preprocessor_linear"]
        prep_tree = self.artifact["preprocessor_tree"]
        weights = self.artifact["ensemble_weights"]

        x_lin = prep_lin.transform(df)
        x_tree = prep_tree.transform(df)

        p_lr = self.artifact["model_lr"].predict_proba(x_lin)[0]
        p_xgb = self.artifact["model_xgb"].predict_proba(x_tree)[0]
        p_lgb = self.artifact["model_lgb"].predict_proba(x_tree)[0]
        p_cb = self.artifact["model_cb"].predict_proba(x_tree)[0]

        # Weighted ensemble
        probs = weights[0] * p_lr + weights[1] * p_xgb + weights[2] * p_lgb + weights[3] * p_cb

        # Normalize to sum to 1
        probs = probs / probs.sum()

        # Sort by probability descending
        sorted_indices = np.argsort(probs)[::-1]
        top_predictions = []
        for idx in sorted_indices[:3]:
            top_predictions.append(
                {
                    "root_cause": classes[idx],
                    "probability": round(float(probs[idx]), 4),
                }
            )

        primary_idx = sorted_indices[0]
        confidence = float(probs[primary_idx])
        confidence = max(0.0, min(1.0, confidence))

        return {
            "root_cause": classes[primary_idx],
            "confidence": round(confidence, 4),
            "top_predictions": top_predictions,
            "confidence_status": self._get_confidence_status(confidence),
            "model_name": self.metadata.get("model_type", "ensemble"),
            "model_version": self.metadata.get("trained_timestamp", "unknown"),
            "is_deterministic": False,
        }

    def _predict_legacy(self, features: dict[str, Any]) -> dict[str, Any]:
        """Predict using a legacy single-model artifact."""
        df = pd.DataFrame([features])
        required_features = self.metadata.get("feature_schema", [])
        for feat in required_features:
            if feat not in df.columns:
                raise ValueError(f"Missing required feature for ML root cause model: {feat}")

        pipeline = self.artifact["pipeline"]
        label_encoder = self.artifact["label_encoder"]

        probs = pipeline.predict_proba(df)[0]
        top_idx = int(probs.argmax())
        confidence = float(probs[top_idx])
        confidence = max(0.0, min(1.0, confidence))

        predicted_class = str(label_encoder.inverse_transform([top_idx])[0])

        return {
            "root_cause": predicted_class,
            "confidence": confidence,
            "top_predictions": [
                {"root_cause": predicted_class, "probability": round(confidence, 4)},
            ],
            "confidence_status": self._get_confidence_status(confidence),
            "model_name": self.metadata.get("model_name", "root_cause"),
            "model_version": self.metadata.get("model_version", "1.0.0"),
            "is_deterministic": False,
        }
