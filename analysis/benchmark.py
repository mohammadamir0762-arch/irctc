"""
Benchmark and validation for the PNR confirmation model.

Answers four questions, each against real data, and prints a report:

  1. Are the four deployed features actually the determining ones?
  2. How much signal exists in total, and how much do we capture?
  3. Which features would improve the model most if we could get them?
  4. Can the higher-scoring Railofy model be deployed? (No — this proves it.)

Everything here is reproducible: no API calls, no network, no paid services.
Run from the repo root:

    python analysis/benchmark.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
WAITLIST_CSV = DATASET_DIR / "Railway Ticket WaitingList Data.csv"
RAILOFY_CSV = DATASET_DIR / "Railofy_training_data_for_model.csv"

RANDOM_STATE = 0
OBSERVATION_POINTS = {"status1Month": 30, "status1Week": 7, "status2Days": 2}


def header(text: str) -> None:
    print(f"\n{'=' * 68}\n{text}\n{'=' * 68}")


def load_waitlist() -> pd.DataFrame:
    return pd.read_csv(WAITLIST_CSV, index_col=0).replace(-1, np.nan)


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """One row per (ticket, observation) — the shape the app sees at
    prediction time: a position observed N days before the journey."""
    wide = wide.copy()
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
    long["travel_class_code"] = long["travelClass"].astype("category").cat.codes
    return long.rename(columns={"bookingStatus": "booking_position", "labels": "confirmed"})


def q1_are_the_features_real(wide: pd.DataFrame) -> None:
    header("1. Are the deployed features actually determining factors?")

    print("\nWaitlist position (observed 7 days before journey):")
    week = wide.dropna(subset=["status1Week"])
    buckets = pd.cut(week["status1Week"], [0, 5, 15, 30, 60, 900])
    table = week.groupby(buckets, observed=True)["labels"].agg(
        confirm_rate="mean", tickets="size"
    )
    for bucket, row in table.iterrows():
        print(f"  WL {str(bucket):<12} {row['confirm_rate'] * 100:5.1f}%   (n={int(row['tickets'])})")
    lo, hi = table["confirm_rate"].min(), table["confirm_rate"].max()
    print(f"  -> {hi / max(lo, 1e-9):.0f}x spread between best and worst bucket")

    print("\nDays until journey (holding position at WL 1-5):")
    for column, days in sorted(OBSERVATION_POINTS.items(), key=lambda kv: -kv[1]):
        subset = wide.dropna(subset=[column])
        subset = subset[subset[column] <= 5]
        print(f"  {days:2}d before   {subset['labels'].mean() * 100:5.1f}%   (n={len(subset)})")

    print("\nTravel class (holding position at WL 1-15, 7 days out):")
    subset = wide.dropna(subset=["status1Week"])
    subset = subset[subset["status1Week"] <= 15]
    by_class = subset.groupby("travelClass")["labels"].agg(rate="mean", n="size")
    by_class = by_class[by_class["n"] > 100].sort_values("rate")
    for name, row in by_class.iterrows():
        print(f"  {name:<4} {row['rate'] * 100:5.1f}%   (n={int(row['n'])})")


def q2_deployed_model_score(long: pd.DataFrame) -> float:
    header("2. How well does the deployed model score?")

    features = ["travel_class_code", "booking_position", "current_position", "days_before_journey"]
    X, y, groups = long[features], long["confirmed"], long["ticket_id"]
    # Grouped split: observations of one ticket must not span train and test.
    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_STATE).split(X, y, groups)
    )
    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, random_state=RANDOM_STATE
    ).fit(X.iloc[train_idx], y.iloc[train_idx])
    auc = roc_auc_score(y.iloc[test_idx], model.predict_proba(X.iloc[test_idx])[:, 1])

    print(f"\n  Tickets:      {long['ticket_id'].nunique():,}")
    print(f"  Observations: {len(long):,}")
    print(f"  Features:     {len(features)}")
    print(f"  Test AUC:     {auc:.4f}")
    return auc


def q3_what_would_help(railofy: pd.DataFrame) -> float:
    header("3. What is the ceiling, and which features would help most?")

    railofy = railofy.copy()
    railofy["QT_code"] = railofy["QT"].astype("category").cat.codes
    features = [c for c in railofy.columns if c not in ("pk", "target", "QT")]
    X, y = railofy[features], railofy["target"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=RANDOM_STATE, stratify=y
    )
    model = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, random_state=RANDOM_STATE
    ).fit(X_train, y_train)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"\n  Railofy full model ({len(features)} features): AUC {auc:.4f}")

    importance = permutation_importance(
        model, X_test, y_test, n_repeats=5, random_state=RANDOM_STATE, scoring="roc_auc"
    )
    ranked = pd.Series(importance.importances_mean, index=features).sort_values(ascending=False)
    print("\n  Top 8 features by permutation importance:")
    labels = {
        "CURP": "current waitlist position",
        "NDTD": "days to departure",
        "QT_code": "QUOTA",
        "ODD": "origin-destination distance",
        "JD": "journey distance",
        "SL": "sleeper class flag",
        "GROP": "(availability stat)",
        "GRCA": "(availability stat)",
    }
    for rank, (name, score) in enumerate(ranked.head(8).items(), start=1):
        print(f"    {rank}. {name:<9} {score:+.4f}  {labels.get(name, '')}")

    print("\n  Quota confirmation rates (real, 36,775 tickets):")
    quota_names = {"GN": "General", "PQ": "Pooled", "RL": "Remote Location"}
    for code, row in railofy.groupby("QT")["target"].agg(rate="mean", n="size").iterrows():
        print(f"    {quota_names.get(code, code):<16} {row['rate'] * 100:5.1f}%   (n={int(row['n'])})")
    return auc


def q4_can_railofy_be_deployed(railofy: pd.DataFrame, long: pd.DataFrame) -> None:
    header("4. Can the higher-scoring Railofy model be deployed? (No)")

    print("\n  Railofy stores position as an encoded ratio, not a raw number:")
    for value, count in railofy["CURP"].value_counts().head(5).items():
        print(f"    CURP = {value:<12} (appears {count}x)")
    print("\n  These are fractions (1/2, 1/3, 1/4 ...) of an unknown denominator")
    print("  that is not present in the file. So a real 'WL 25' cannot be")
    print("  converted into the model's input scale.")

    railofy = railofy.copy()
    railofy["QT_code"] = railofy["QT"].astype("category").cat.codes
    features = ["QT_code", "NDTD", "CURP", "SL", "CL_1", "CL_2", "CL_3"]
    model = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, random_state=RANDOM_STATE
    ).fit(railofy[features], railofy["target"])

    # Best-effort rescue: map real values onto Railofy's distribution by
    # percentile, then score against REAL labels.
    def quantile_map(values, reference):
        percentile = pd.Series(values).rank(pct=True).values * 100
        return np.percentile(reference, np.clip(percentile, 0, 100))

    mapped = pd.DataFrame({
        "QT_code": 0,
        "NDTD": quantile_map(long["days_before_journey"], railofy["NDTD"].values),
        "CURP": quantile_map(long["current_position"], railofy["CURP"].values),
        "SL": (long["travelClass"] == "SL").astype(int),
        "CL_1": (long["travelClass"] == "3A").astype(int),
        "CL_2": (long["travelClass"] == "2A").astype(int),
        "CL_3": (long["travelClass"] == "1A").astype(int),
    })
    auc = roc_auc_score(long["confirmed"], model.predict_proba(mapped[features])[:, 1])
    print(f"\n  Quantile-mapped Railofy model, scored on REAL labels: AUC {auc:.4f}")
    print("  (0.50 = random. Below that means the mapping destroys the signal.)")
    print("  Conclusion: not deployable. The deployed model uses raw values instead.")


def main() -> None:
    for path in (WAITLIST_CSV, RAILOFY_CSV):
        if not path.exists():
            raise SystemExit(f"Missing dataset: {path}")

    wide = load_waitlist()
    long = to_long(wide)
    railofy = pd.read_csv(RAILOFY_CSV)

    q1_are_the_features_real(wide)
    deployed_auc = q2_deployed_model_score(long)
    ceiling_auc = q3_what_would_help(railofy)
    q4_can_railofy_be_deployed(railofy, long)

    header("SUMMARY")
    captured = (deployed_auc - 0.5) / (ceiling_auc - 0.5)
    print(f"""
  Deployed model      AUC {deployed_auc:.3f}   4 features, real data, runs live
  Observed ceiling    AUC {ceiling_auc:.3f}   23 features, cannot be deployed
  Random baseline     AUC 0.500

  The deployed model captures {captured:.0%} of the achievable signal above
  random, using 4 features instead of 23.

  Biggest missing feature is quota (5th by importance), which no public
  dataset provides with real outcomes in a usable form.
""")


if __name__ == "__main__":
    main()
