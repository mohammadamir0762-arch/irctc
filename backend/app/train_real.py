"""
Trains the confirmation-probability model on REAL waitlist data.

Source: dataset/Railway Ticket WaitingList Data.csv (Kaggle). Each row is one
real waitlisted ticket, with its waitlist position recorded at booking and
again at ~1 month / 1 week / 2 days / 1 day before the journey, plus whether
it ultimately confirmed.

This replaces the earlier synthetic model, which was circular: it was trained
on labels produced by a hand-written formula, so it could only re-learn that
formula. Numbers from this model are measured against real outcomes.

Reshaping: the source is wide (one row per ticket, one column per observation
time). We melt it to long — one row per (ticket, observation) — because that
matches what the app actually has at prediction time: a position observed
some number of days before the journey. Train/test splits are grouped by
ticket so observations of the same ticket never straddle the split.

Run: python -m app.train_real
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent / "dataset" / "Railway Ticket WaitingList Data.csv"
)
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Column -> how many days before the journey that observation was taken.
#
# `status1Day` is deliberately EXCLUDED. In the source it has ~30k rows (more
# than double the others), a 0.3% confirmation rate, and — decisively — no
# relationship between position and outcome (flat ~0.2-0.3% from WL 1 through
# WL 900, where every other observation point falls steeply with position).
# Whatever that column records, it is not "waitlist position 1 day out", and
# training on it just teaches the model a data artifact.
OBSERVATION_POINTS = {
    "status1Month": 30,
    "status1Week": 7,
    "status2Days": 2,
}

TRAVEL_CLASSES = ["SL", "3A", "2A", "CC", "1A", "2S"]
FEATURE_COLUMNS = ["travel_class_code", "booking_position", "current_position", "days_before_journey"]
MISSING = -1  # the source encodes "not observed" as -1


def load_long_format() -> pd.DataFrame:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Real dataset not found at {DATASET_PATH}. "
            "Download 'Railway Waitinglist Dataset' from Kaggle into dataset/."
        )
    wide = pd.read_csv(DATASET_PATH, index_col=0).replace(MISSING, np.nan)
    wide["ticket_id"] = np.arange(len(wide))

    frames = []
    for column, days in OBSERVATION_POINTS.items():
        frame = wide[["travelClass", "bookingStatus", column, "labels", "ticket_id"]].dropna(
            subset=[column]
        )
        frame = frame.rename(columns={column: "current_position"})
        frame["days_before_journey"] = days
        frames.append(frame)

    long = pd.concat(frames, ignore_index=True)
    long = long.rename(columns={"bookingStatus": "booking_position", "labels": "confirmed"})
    long["travel_class_code"] = long["travelClass"].apply(
        lambda c: TRAVEL_CLASSES.index(c) if c in TRAVEL_CLASSES else -1
    )
    return long


def main():
    long = load_long_format()
    print(f"Loaded {len(long)} observations from {long['ticket_id'].nunique()} real tickets.")
    print(f"Confirmation rate: {long['confirmed'].mean():.1%}")

    X = long[FEATURE_COLUMNS]
    y = long["confirmed"]
    groups = long["ticket_id"]

    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=0).split(X, y, groups)
    )
    model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, random_state=0)
    model.fit(X.iloc[train_idx], y.iloc[train_idx])

    proba = model.predict_proba(X.iloc[test_idx])[:, 1]
    y_test = y.iloc[test_idx]
    print(f"\nTest AUC:   {roc_auc_score(y_test, proba):.4f}")
    print(f"Test Brier: {brier_score_loss(y_test, proba):.4f}")

    print("\nAUC by when the check happens:")
    days_test = X.iloc[test_idx]["days_before_journey"].values
    for days in sorted(OBSERVATION_POINTS.values(), reverse=True):
        mask = days_test == days
        if mask.sum() > 50:
            print(f"  {days:2}d before: AUC={roc_auc_score(y_test[mask], proba[mask]):.4f}  (n={mask.sum()})")

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODELS_DIR / "model.joblib")

    metadata = {
        "trained_on": "real",
        "source": "Kaggle Railway Waitinglist Dataset",
        "n_observations": int(len(long)),
        "n_tickets": int(long["ticket_id"].nunique()),
        "test_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "test_brier": round(float(brier_score_loss(y_test, proba)), 4),
        "feature_columns": FEATURE_COLUMNS,
        "travel_classes": TRAVEL_CLASSES,
        "reference": {
            "travel_class_code": int(long["travel_class_code"].mode()[0]),
            "booking_position": float(long["booking_position"].median()),
            "current_position": float(long["current_position"].median()),
            "days_before_journey": 7,
        },
    }
    with open(MODELS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model to {MODELS_DIR / 'model.joblib'}")
    print(f"Saved metadata to {MODELS_DIR / 'metadata.json'}")


if __name__ == "__main__":
    main()
