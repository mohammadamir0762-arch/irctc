"""
SQLite-backed log of every PNR check, plus outcome polling.

This is the "data flywheel" from the project discussion: real historical
IRCTC outcome data doesn't exist publicly, so every check a real user makes
gets logged with its feature snapshot, then re-checked after the journey
date to capture what actually happened. Once enough real (features, outcome)
rows exist, they replace the synthetic training set in train.py.

SQLite is deliberately the whole "database" here — free, zero setup, and
enough for an MVP's write volume. Swap for Postgres (e.g. Supabase/Neon
free tier) once this needs concurrent writers or lives on a real server.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pnr_log.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pnr_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pnr_number TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    journey_date TEXT,
    train_number TEXT,
    travel_class TEXT,
    quota TEXT,
    train_category TEXT,
    booking_position INTEGER,
    current_position INTEGER,
    days_before_journey INTEGER,
    rac_flag INTEGER,
    predicted_probability REAL,
    is_mock INTEGER NOT NULL,
    outcome_status TEXT,
    outcome_checked_at TEXT
);
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_check(
    pnr_number: str,
    is_mock: bool,
    resolved_status: str | None = None,
    journey_date: str | None = None,
    train_number: str | None = None,
    features: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    predicted_probability: float | None = None,
) -> None:
    features = features or {}
    context = context or {}
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO pnr_checks (
                pnr_number, checked_at, journey_date, train_number,
                travel_class, quota, train_category,
                booking_position, current_position, days_before_journey,
                rac_flag, predicted_probability, is_mock,
                outcome_status, outcome_checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pnr_number,
                datetime.now().isoformat(),
                journey_date,
                train_number,
                context.get("travel_class"),
                context.get("quota"),
                context.get("train_category"),
                features.get("booking_position"),
                features.get("current_position"),
                features.get("days_before_journey"),
                int(context["rac_flag"]) if "rac_flag" in context else None,
                predicted_probability,
                int(is_mock),
                resolved_status,
                datetime.now().isoformat() if resolved_status else None,
            ),
        )


def pending_outcome_rows() -> list[sqlite3.Row]:
    """Rows that were unresolved (WL/RAC) at check time, whose journey date
    has passed, and haven't had their outcome captured yet."""
    today = datetime.now().date().isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM pnr_checks
            WHERE outcome_status IS NULL
              AND journey_date IS NOT NULL
              AND date(journey_date) <= date(?)
            """,
            (today,),
        )
        return cursor.fetchall()


def record_outcome(row_id: int, outcome_status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE pnr_checks SET outcome_status = ?, outcome_checked_at = ? WHERE id = ?",
            (outcome_status, datetime.now().isoformat(), row_id),
        )


def stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM pnr_checks").fetchone()[0]
        with_outcome = conn.execute(
            "SELECT COUNT(*) FROM pnr_checks WHERE outcome_status IS NOT NULL"
        ).fetchone()[0]
        real = conn.execute("SELECT COUNT(*) FROM pnr_checks WHERE is_mock = 0").fetchone()[0]
    return {"total_checks": total, "checks_with_outcome": with_outcome, "real_checks": real}
