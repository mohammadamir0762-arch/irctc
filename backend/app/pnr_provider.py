"""
Fetches PNR status from a third-party provider.

There is no official IRCTC bulk data API, so this goes through third-party
wrappers. Providers disagree on field names and response shape, so each
provider class is responsible for normalising its own response into the
canonical shape below; everything downstream (pnr_mapper.py) only ever sees
the canonical shape.

Canonical shape:
    {
        "PnrNumber": str,
        "TrainNumber": str,
        "TrainName": str,
        "JourneyClass": str,          # "SL" / "3A" / ...
        "Quota": str,                 # "GN" / "CK" / ... ("" if not supplied)
        "ChatPrepared": "YES"|"NO",
        "From": str,
        "To": str,
        "JourneyDate": "DD-MM-YYYY",
        "Passangers": [{"BookingStatus": str, "CurrentStatus": str}],
    }
`CurrentStatus` may be slash-delimited ("CNF/S6/71/GN", "GNWL/-/16/GN") or
bare/space-delimited ("CNF", "WL 12"); pnr_mapper handles both. When a
provider omits the quota from the status string it must supply the
top-level "Quota" field instead.

Selecting a provider (see README "Choosing a provider"):
    PNR_PROVIDER=mock            (default when no key is set)
    PNR_PROVIDER=indianrailapi   + PNR_API_KEY=...
    PNR_PROVIDER=rapidapi        + PNR_API_KEY=... + PNR_RAPIDAPI_HOST=...

If a provider's real response doesn't match what the adapter expects, run
`python -m app.test_provider <pnr>` — it prints the raw response next to the
normalised one so the mapping can be corrected quickly.
"""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Protocol

import requests

REQUEST_TIMEOUT = 10

MOCK_TRAIN_NAMES = ["RAJDHANI EXP", "GARIB RATH", "SF EXPRESS", "PASSENGER", "SHATABDI EXP"]
MOCK_CLASSES = ["SL", "3A", "2A", "1A", "CC"]
MOCK_QUOTA_CODES = ["GN", "TQ", "LD", "SS"]


class PNRProviderError(Exception):
    pass


class PNRProvider(Protocol):
    name: str

    def fetch(self, pnr_number: str) -> dict: ...


def _first(payload: dict, *keys, default=None):
    """Return the first present, non-empty value among `keys`.

    Providers name the same field differently (TrainNo/train_number/trainNumber),
    so adapters use this instead of hardcoding one spelling.
    """
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", []):
            return value
    return default


class IndianRailAPIProvider:
    """indianrailapi.com — documented endpoint, returns the canonical shape
    almost as-is (it is what the canonical shape was modelled on)."""

    name = "indianrailapi"
    BASE_URL = "https://indianrailapi.com/api/v2/PNRCheck/apikey/{key}/PNRNumber/{pnr}/"

    def __init__(self, api_key: str):
        if not api_key:
            raise PNRProviderError("PNR_API_KEY is required for the indianrailapi provider.")
        self.api_key = api_key

    def fetch(self, pnr_number: str) -> dict:
        url = self.BASE_URL.format(key=self.api_key, pnr=pnr_number)
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise PNRProviderError(f"indianrailapi request failed: {e}") from e
        except ValueError as e:
            raise PNRProviderError(f"indianrailapi returned non-JSON: {e}") from e

        if str(data.get("Status", "")).upper() != "SUCCESS":
            raise PNRProviderError(data.get("Message") or "PNR lookup failed")
        return data


class RapidAPIProvider:
    """Generic adapter for the various IRCTC/PNR listings on RapidAPI.

    Those listings share an auth scheme (x-rapidapi-key / x-rapidapi-host
    headers) but NOT a response schema, so this normalises best-effort
    across the field spellings commonly seen. Verify against your chosen
    listing with `python -m app.test_provider <pnr>` and adjust the key
    names below if they differ — that is expected, not a failure.
    """

    name = "rapidapi"

    def __init__(self, api_key: str, host: str, path: str | None = None):
        if not api_key:
            raise PNRProviderError("PNR_API_KEY is required for the rapidapi provider.")
        if not host:
            raise PNRProviderError(
                "PNR_RAPIDAPI_HOST is required for the rapidapi provider "
                "(e.g. 'irctc1.p.rapidapi.com' — copy it from the listing's code snippet)."
            )
        self.api_key = api_key
        self.host = host
        # Path varies per listing; override with PNR_RAPIDAPI_PATH.
        self.path = path or "/api/v3/getPNRStatus"

    def fetch(self, pnr_number: str) -> dict:
        url = f"https://{self.host}{self.path}"
        try:
            response = requests.get(
                url,
                headers={"x-rapidapi-key": self.api_key, "x-rapidapi-host": self.host},
                params={"pnrNumber": pnr_number},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise PNRProviderError(f"rapidapi request failed: {e}") from e
        except ValueError as e:
            raise PNRProviderError(f"rapidapi returned non-JSON: {e}") from e

        # These listings signal failure in the body with HTTP 200, e.g.
        # {"status": false, "message": "PNR Not found."} — surface that
        # message rather than letting _normalise fail confusingly.
        if data.get("status") is False:
            raise PNRProviderError(data.get("message") or "PNR lookup failed")

        return self._normalise(data, pnr_number)

    def _normalise(self, data: dict, pnr_number: str) -> dict:
        # Most listings nest the useful payload under "data"; some don't.
        payload: dict[str, Any] = data.get("data") if isinstance(data.get("data"), dict) else data

        raw_passengers = _first(
            payload, "passengerList", "PassengerStatus", "Passangers", "passengers", default=[]
        )
        passengers = []
        for p in raw_passengers:
            if not isinstance(p, dict):
                continue
            current = str(
                _first(p, "currentStatus", "CurrentStatus", "current_status", default="")
            )
            # irctc1 returns a bare status ("WL") with the queue position in a
            # separate field, so re-attach it — pnr_mapper needs the position
            # to score a waitlisted ticket.
            if current and not any(ch.isdigit() for ch in current):
                position = _first(p, "CurrentBerthNo", "currentBerthNo", default="")
                if str(position).strip().isdigit():
                    current = f"{current} {str(position).strip()}"
            passengers.append({
                "BookingStatus": str(
                    _first(p, "bookingStatus", "BookingStatus", "booking_status", default="")
                ),
                "CurrentStatus": current,
            })

        if not passengers:
            raise PNRProviderError(
                "Could not find passenger status in the rapidapi response. "
                "Run `python -m app.test_provider <pnr>` to inspect the raw shape "
                "and adjust RapidAPIProvider._normalise()."
            )

        chart_raw = _first(payload, "chartPrepared", "ChartPrepared", "chart_prepared", default=False)
        chart_prepared = chart_raw if isinstance(chart_raw, bool) else str(chart_raw).upper() in ("YES", "TRUE", "1")

        # Key lookups are case-sensitive, so every observed spelling is listed
        # explicitly — irctc1 uses "Pnr"/"TrainNo"/"Class"/"Doj".
        return {
            "PnrNumber": str(_first(payload, "Pnr", "pnrNumber", "PnrNumber", default=pnr_number)),
            "TrainNumber": str(_first(payload, "TrainNo", "trainNumber", "TrainNumber", default="")),
            "TrainName": str(_first(payload, "TrainName", "trainName", default="")),
            "JourneyClass": str(
                _first(payload, "Class", "JourneyClass", "journeyClass", "class", default="SL")
            ).upper(),
            "Quota": str(_first(payload, "Quota", "quota", default="")).upper(),
            "ChatPrepared": "YES" if chart_prepared else "NO",
            "From": str(
                _first(payload, "BoardingStationName", "From", "sourceStation", "boardingPoint", default="")
            ),
            "To": str(
                _first(payload, "ReservationUptoName", "To", "destinationStation", "reservationUpto", default="")
            ),
            "JourneyDate": self._normalise_date(
                _first(payload, "Doj", "dateOfJourney", "doj", "JourneyDate", default="")
            ),
            "Passangers": passengers,
        }

    @staticmethod
    def _normalise_date(value: Any) -> str:
        """Coerce the assorted date formats providers return into DD-MM-YYYY,
        which is what pnr_mapper expects."""
        text = str(value).strip()
        if not text:
            raise PNRProviderError("rapidapi response had no journey date.")
        # Some listings return "12-08-2026 10:30" or ISO timestamps.
        text = text.split("T")[0].split(" ")[0]
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%d-%m-%Y")
            except ValueError:
                continue
        raise PNRProviderError(f"Unrecognised journey date format from rapidapi: {value!r}")


class MockPNRProvider:
    """Deterministic per-PNR fake data so demos are stable and repeatable
    without a real API key. Clearly not real IRCTC data — do not use for
    anything beyond local development."""

    name = "mock"

    def fetch(self, pnr_number: str) -> dict:
        seed = int(hashlib.sha256(pnr_number.encode()).hexdigest(), 16)
        train_name = MOCK_TRAIN_NAMES[seed % len(MOCK_TRAIN_NAMES)]
        journey_class = MOCK_CLASSES[(seed // 7) % len(MOCK_CLASSES)]
        quota_code = MOCK_QUOTA_CODES[(seed // 13) % len(MOCK_QUOTA_CODES)]
        wl_position = (seed // 17) % 80
        is_rac = wl_position % 9 == 0
        chart_prepared = wl_position % 23 == 0
        journey_date = datetime.now() + timedelta(days=(seed // 29) % 45 + 1)

        status_type = "CNF" if chart_prepared else ("RAC" if is_rac else "GNWL")
        current_status = f"{status_type}/-/{ wl_position if status_type != 'CNF' else 1}/{quota_code}"

        return {
            "PnrNumber": pnr_number,
            "Status": "SUCCESS",
            "ResponseCode": "200",
            "TrainNumber": str(10000 + seed % 9000),
            "TrainName": train_name,
            "JourneyClass": journey_class,
            "ChatPrepared": "YES" if chart_prepared else "NO",
            "From": "SOURCE STATION [SRC]",
            "To": "DEST STATION [DST]",
            "JourneyDate": journey_date.strftime("%d-%m-%Y"),
            "Passangers": [
                {
                    "Passenger": "Passenger 1",
                    "BookingStatus": f"GNWL/-/{wl_position + 20}/{quota_code}",
                    "CurrentStatus": current_status,
                }
            ],
            "_is_mock": True,
        }


def get_provider() -> PNRProvider:
    api_key = os.environ.get("PNR_API_KEY", "").strip()
    # Default to whichever provider makes sense: mock without a key, and the
    # documented one with a key, so setting PNR_API_KEY alone is enough.
    provider_name = os.environ.get("PNR_PROVIDER", "").strip().lower()
    if not provider_name:
        provider_name = "indianrailapi" if api_key else "mock"

    if provider_name == "mock":
        return MockPNRProvider()
    if provider_name == "indianrailapi":
        return IndianRailAPIProvider(api_key)
    if provider_name == "rapidapi":
        return RapidAPIProvider(
            api_key,
            host=os.environ.get("PNR_RAPIDAPI_HOST", "").strip(),
            path=os.environ.get("PNR_RAPIDAPI_PATH", "").strip() or None,
        )
    raise PNRProviderError(
        f"Unknown PNR_PROVIDER {provider_name!r}. Expected one of: mock, indianrailapi, rapidapi."
    )
