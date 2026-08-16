"""
Loads the trained model and serves predictions plus a per-prediction
explanation.

The model is trained on real waitlist outcomes (see train_real.py), so its
inputs are only what real data actually supports: travel class, waitlist
position at booking, current waitlist position, and how many days remain
before the journey.

Explanation method: for each feature, swap in a "neutral" reference value
(the training set's median/mode) and measure how much the predicted
probability shifts. Ranking by that shift is a cheap occlusion-based
approximation of feature attribution — not as rigorous as SHAP, but
dependency-free and enough to show "why" alongside a number.
"""

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
_MODEL_PATH = MODELS_DIR / "model.joblib"
_METADATA_PATH = MODELS_DIR / "metadata.json"

FACTOR_LABELS = {
    "current_position": "Current waitlist position",
    "booking_position": "Waitlist position when booked",
    "days_before_journey": "Days until journey",
    "travel_class_code": "Travel class",
}


class PredictionService:
    def __init__(self):
        if not _MODEL_PATH.exists() or not _METADATA_PATH.exists():
            raise FileNotFoundError(
                f"No trained model found in {MODELS_DIR}. Run `python -m app.train_real` first."
            )
        self.pipeline = joblib.load(_MODEL_PATH)
        with open(_METADATA_PATH) as f:
            self.metadata = json.load(f)
        self.feature_columns: list[str] = self.metadata["feature_columns"]
        self.travel_classes: list[str] = self.metadata["travel_classes"]
        self.reference: dict[str, Any] = self.metadata["reference"]

    def class_code(self, travel_class: str) -> int:
        """-1 for classes the training data never saw; the model treats it as
        its own category rather than silently pretending it was Sleeper."""
        return self.travel_classes.index(travel_class) if travel_class in self.travel_classes else -1

    def _to_frame(self, features: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame([{col: features[col] for col in self.feature_columns}])

    def predict(self, features: dict[str, Any]) -> float:
        return float(self.pipeline.predict_proba(self._to_frame(features))[0, 1])

    def top_factors(self, features: dict[str, Any], base_probability: float, top_n: int = 3):
        impacts = []
        for col in self.feature_columns:
            if features[col] == self.reference[col]:
                continue
            neutral = dict(features)
            neutral[col] = self.reference[col]
            delta = base_probability - self.predict(neutral)
            impacts.append((col, delta))

        impacts.sort(key=lambda item: abs(item[1]), reverse=True)
        factors = []
        for col, delta in impacts[:top_n]:
            direction = "increases" if delta > 0 else "decreases"
            factors.append({
                "factor": FACTOR_LABELS.get(col, col),
                "impact": f"{direction} confirmation chance by ~{abs(delta) * 100:.1f} pts",
            })
        return factors


_service: PredictionService | None = None


def get_service() -> PredictionService:
    global _service
    if _service is None:
        _service = PredictionService()
    return _service
