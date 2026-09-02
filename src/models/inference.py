import json
import os
from typing import Any

import joblib
import pandas as pd


class RiskInferenceService:
    """Service to load the Risk Model and perform inference."""

    def __init__(
        self,
        model_path: str = "artifacts/models/revenue_risk_model.joblib",
        metadata_path: str = "artifacts/models/revenue_risk_metadata.json",
    ):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.model = None
        self.metadata = None
        self._load_model()

    def _load_model(self) -> None:
        if not os.path.exists(self.model_path) or not os.path.exists(self.metadata_path):
            raise FileNotFoundError(
                f"Model or metadata not found at {self.model_path} / {self.metadata_path}"
            )

        self.model = joblib.load(self.model_path)
        with open(self.metadata_path) as f:
            self.metadata = json.load(f)

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Perform inference for a single case.
        Contract requires:
        {
          "prediction": <float_uncalibrated_or_class>,
          "confidence": <float_calibrated>,
          "model_name": "...",
          "model_version": "..."
        }
        As specified by interpretation, we output the raw probability as prediction
        and the calibrated probability as confidence, or since CalibratedClassifierCV
        returns calibrated probability on predict_proba, we use prediction=class, confidence=prob.
        Wait, for probability we output prediction as probability. Let's output prediction as binary class and confidence as probability.
        """
        if not self.model or not self.metadata:
            raise RuntimeError("Model is not loaded.")

        # Convert single dict to DataFrame for the sklearn pipeline
        df = pd.DataFrame([features])

        # Verify schema
        required_features = self.metadata.get("configuration", {}).get("features", [])
        for f in required_features:
            if f not in df.columns:
                raise ValueError(f"Missing required feature: {f}")

        # The model is a CalibratedClassifierCV which outputs calibrated probabilities
        # on predict_proba and class on predict.
        prob = float(self.model.predict_proba(df)[0, 1])
        pred_class = float(self.model.predict(df)[0])

        return {
            "prediction": pred_class,
            "confidence": prob,
            "model_name": self.metadata.get("model_name", "revenue_risk"),
            "model_version": self.metadata.get("model_version", "1.0.0"),
        }
