"""Recovery propensity inference service."""

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.database.models import Customer, Payment, RecoveryCase
from src.features.recovery_features import RecoveryPropensityFeatureExtractor


class RecoveryPropensityModel:
    """Predicts recovery probability using the trained XGBoost model."""

    def __init__(self, model_dir: str = "artifacts/models") -> None:
        self.model_dir = Path(model_dir)
        self.model: Any = None
        self.metadata: dict[str, Any] = {}
        self.extractor = RecoveryPropensityFeatureExtractor()

        # Determine model to load
        self.model_path = self.model_dir / "recovery_propensity_model.pkl"
        self.metadata_path = self.model_dir / "recovery_model_metadata.json"

    def load(self) -> None:
        """Load the model and metadata from disk."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        self.model = joblib.load(self.model_path)

        if self.metadata_path.exists():
            with open(self.metadata_path, encoding="utf-8") as f:
                self.metadata = json.load(f)

    def _ensure_loaded(self) -> None:
        if self.model is None:
            self.load()

    def predict(
        self,
        case: RecoveryCase,
        customer: Customer,
        action_type: str,
        attempt_number: int = 1,
        trigger_payment: Payment | None = None,
    ) -> dict[str, Any]:
        """Predict recovery probability for a candidate action.

        Returns:
            dict with recovery_probability, confidence, model_version
        """
        self._ensure_loaded()

        # 1. Extract features
        features = self.extractor.extract(
            case=case,
            customer=customer,
            action_type=action_type,
            attempt_number=attempt_number,
            trigger_payment=trigger_payment,
        )

        # 2. DataFrame formatting
        df = pd.DataFrame([features])

        # Make categorical
        if "action_type" in df.columns:
            df["action_type"] = df["action_type"].astype("category")
        if "root_cause" in df.columns:
            df["root_cause"] = df["root_cause"].astype("category")

        # Ensure correct column order if metadata exists
        if self.metadata and "features" in self.metadata:
            for col in self.metadata["features"]:
                if col not in df.columns:
                    df[col] = 0.0
            df = df[self.metadata["features"]]

        # 3. Predict
        assert self.model is not None, "Model is not loaded"
        proba = self.model.predict_proba(df)[0]

        # Class 1 is success
        if hasattr(self.model, "classes_"):
            class_1_idx = list(self.model.classes_).index(1) if 1 in self.model.classes_ else 1
            if class_1_idx >= len(proba):
                class_1_idx = -1
        else:
            class_1_idx = 1

        recovery_prob = float(proba[class_1_idx])

        # Heuristic confidence: distance from 0.5 (scaled to 0-1)
        # Closer to 0 or 1 means more confident
        confidence = float(abs(recovery_prob - 0.5) * 2.0)

        return {
            "recovery_probability": recovery_prob,
            "confidence": confidence,
            "model_version": self.metadata.get("version", "1.0.0"),
        }
