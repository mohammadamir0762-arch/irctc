"""
Outcome-polling job for the data flywheel: for every logged PNR check that
was unresolved (WL/RAC) at check time and is now past its journey date,
re-fetch the current status and record what actually happened. This is
what turns logged checks into real (features, outcome) training rows.

Intended to run periodically (e.g. a daily cron) once PNR_API_KEY points at
a real provider — polling mock PNRs is harmless but won't show real
progression, since the mock provider is deterministic per-PNR.

Run: python -m app.poll_outcomes
"""

from app import storage
from app.pnr_provider import PNRProviderError, get_provider


def classify_outcome(current_status: str) -> str | None:
    status_type = current_status.split("/")[0]
    if status_type == "CNF":
        return "Confirmed"
    if status_type in ("CAN", "MOD"):
        return "Cancelled"
    if status_type == "RAC":
        return "RAC"
    if "WL" in status_type:
        return None  # chart likely not prepared/reflected yet — leave pending
    return None


def main():
    provider = get_provider()
    rows = storage.pending_outcome_rows()
    print(f"{len(rows)} PNR(s) pending outcome capture.")

    updated = 0
    for row in rows:
        try:
            raw = provider.fetch(row["pnr_number"])
        except PNRProviderError as e:
            print(f"  {row['pnr_number']}: fetch failed ({e})")
            continue

        passenger = raw["Passangers"][0]
        outcome = classify_outcome(passenger["CurrentStatus"])
        if outcome is None:
            print(f"  {row['pnr_number']}: still unresolved, leaving pending")
            continue

        storage.record_outcome(row["id"], outcome)
        updated += 1
        print(f"  {row['pnr_number']}: outcome = {outcome}")

    print(f"Updated {updated} row(s).")


if __name__ == "__main__":
    main()
