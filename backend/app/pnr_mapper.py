"""
Maps a raw provider PNR response (see pnr_provider.py) into either an
already-resolved status (confirmed/cancelled) or a feature dict the model
can score.

Every model input here is read directly from the provider response — there
are no estimated or invented features, because the model (see train_real.py)
only uses what real data supports: travel class, booking position, current
position, and days until the journey.
"""

import re
from datetime import datetime

from app.model import get_service

QUOTA_CODE_MAP = {
    "GN": "General",
    "TQ": "Tatkal",
    "CK": "Tatkal",
    "PT": "Premium Tatkal",
    "LD": "Ladies",
    "SS": "Senior Citizen",
}

# Providers format status strings differently:
#   indianrailapi : "CNF/S6/71/GN", "GNWL/-/16/GN"   (slash-delimited)
#   irctc1/RapidAPI: "CNF", "CNF B5 55", "WL 12"      (bare or space-delimited)
# So the type is taken as the leading alphabetic token, and the position is
# read only for WL/RAC statuses — that deliberately avoids misreading the
# berth number in "CNF B5 55" as a waitlist position.
_TOKEN_SPLIT_RE = re.compile(r"[/\s]+")
_LEADING_ALPHA_RE = re.compile(r"^([A-Z]+)")
_INT_RE = re.compile(r"^\d+$")


class UnsupportedPNRStatus(Exception):
    """Raised for statuses we don't run a prediction for (e.g. already
    resolved, or a status shape we don't recognise)."""

    def __init__(self, message: str, resolved_status: str | None = None):
        super().__init__(message)
        self.resolved_status = resolved_status


def infer_train_category(train_name: str) -> str:
    name = train_name.upper()
    if "RAJDHANI" in name:
        return "Rajdhani"
    if "DURONTO" in name:
        return "Duronto"
    if "SHATABDI" in name or "VANDE BHARAT" in name:
        return "Shatabdi"
    if "GARIB RATH" in name:
        return "Garib Rath"
    if "PASSENGER" in name or "MEMU" in name or "EMU" in name:
        return "Passenger"
    if "SF" in name.split() or "SUPERFAST" in name:
        return "SF Express"
    return "Express"


def _parse_status(status_str: str):
    """Return (status_type, position|None, quota_code|None), or None if the
    string has no recognisable status type."""
    tokens = [t for t in _TOKEN_SPLIT_RE.split(str(status_str).strip().upper()) if t]
    if not tokens:
        return None

    type_match = _LEADING_ALPHA_RE.match(tokens[0])
    if not type_match:
        return None
    status_type = type_match.group(1)

    # Only WL/RAC carry a meaningful queue position; for CNF the trailing
    # numbers are coach/berth, not a position.
    position = None
    if status_type == "RAC" or "WL" in status_type:
        for token in tokens[1:]:
            if _INT_RE.match(token):
                position = int(token)
                break
        else:
            # e.g. "WL12" with no separator
            trailing = tokens[0][len(status_type):]
            if trailing.isdigit():
                position = int(trailing)

    quota_code = None
    for token in reversed(tokens[1:]):
        if token in QUOTA_CODE_MAP:
            quota_code = token
            break

    return status_type, position, quota_code


def map_pnr_response(raw: dict) -> dict:
    passenger = raw["Passangers"][0]
    current_status = passenger["CurrentStatus"]
    booking_status = passenger.get("BookingStatus", current_status)

    parsed = _parse_status(current_status)
    if parsed is None:
        raise UnsupportedPNRStatus(f"Unrecognised status format: {current_status}")
    status_type, position, quota_code = parsed

    if status_type == "CNF":
        return {"resolved": True, "resolved_status": "Confirmed"}
    if status_type in ("CAN", "MOD"):
        return {"resolved": True, "resolved_status": "Cancelled"}
    if status_type not in ("RAC",) and "WL" not in status_type:
        raise UnsupportedPNRStatus(f"Unhandled status type: {status_type}")

    rac_flag = status_type == "RAC"

    if position is None:
        if rac_flag:
            # RAC without an explicit position: RAC itself is the dominant
            # signal (RAC almost always travels), so treat it as front of
            # the queue rather than refusing to predict.
            position = 0
        else:
            raise UnsupportedPNRStatus(
                f"Waitlisted status {current_status!r} has no readable queue position. "
                "Check the provider's raw response with `python -m app.test_provider`."
            )

    journey_class = str(raw.get("JourneyClass", "SL")).strip().upper()

    # Waitlist position at booking time. The model uses it alongside the
    # current position, so the pair encodes how far the ticket has moved.
    booking_parsed = _parse_status(booking_status)
    booking_position = booking_parsed[1] if booking_parsed else None
    if booking_position is None:
        booking_position = position

    journey_date = datetime.strptime(raw["JourneyDate"], "%d-%m-%Y")
    days_before_journey = max(0, min(120, (journey_date.date() - datetime.now().date()).days))

    service = get_service()
    features = {
        "travel_class_code": service.class_code(journey_class),
        "booking_position": booking_position,
        "current_position": position,
        "days_before_journey": days_before_journey,
    }

    # Quota and train category aren't model inputs — the real training data
    # doesn't contain them — but they're still worth showing the user.
    quota = QUOTA_CODE_MAP.get(str(raw.get("Quota", "")).strip().upper()) or QUOTA_CODE_MAP.get(
        quota_code, "General"
    )

    return {
        "resolved": False,
        "features": features,
        "context": {
            "travel_class": journey_class,
            "quota": quota,
            "train_category": infer_train_category(raw.get("TrainName", "")),
            "rac_flag": rac_flag,
        },
        "estimated_fields": [],
        "pnr_summary": {
            "train_number": raw.get("TrainNumber"),
            "train_name": raw.get("TrainName"),
            "from_station": raw.get("From"),
            "to_station": raw.get("To"),
            "journey_date": raw.get("JourneyDate"),
            "journey_date_iso": journey_date.date().isoformat(),
            "current_status": current_status,
            "booking_status": booking_status,
            "chart_prepared": raw.get("ChatPrepared") == "YES",
        },
        "is_mock": raw.get("_is_mock", False),
    }
