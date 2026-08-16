"""
Diagnostic for a real PNR provider.

Providers differ in response shape, and their docs are often out of date or
login-gated. Rather than guessing, point this at a real PNR with your key
set and it prints, in order:

  1. which provider was selected and why
  2. the raw response the provider returned
  3. the canonical shape after the adapter normalised it
  4. the model features pnr_mapper derived from it
  5. the resulting prediction

If step 2 works but step 3/4 fails, the adapter's field mapping needs
adjusting for your listing — the raw dump shows exactly which names to use
(edit RapidAPIProvider._normalise in pnr_provider.py).

Run:
    export PNR_API_KEY=your_key
    export PNR_PROVIDER=indianrailapi      # or rapidapi
    python -m app.test_provider 1234567890
"""

import json
import os
import sys

from app.pnr_mapper import UnsupportedPNRStatus, map_pnr_response
from app.pnr_provider import PNRProviderError, get_provider


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.test_provider <10-digit-pnr>")
        return 2

    pnr_number = sys.argv[1].strip()
    if not (pnr_number.isdigit() and len(pnr_number) == 10):
        print(f"'{pnr_number}' is not a 10-digit PNR number.")
        return 2

    _section("1. Provider selection")
    key_set = bool(os.environ.get("PNR_API_KEY", "").strip())
    print(f"PNR_PROVIDER      = {os.environ.get('PNR_PROVIDER') or '(unset)'}")
    print(f"PNR_API_KEY       = {'set' if key_set else '(unset)'}")
    print(f"PNR_RAPIDAPI_HOST = {os.environ.get('PNR_RAPIDAPI_HOST') or '(unset)'}")
    try:
        provider = get_provider()
    except PNRProviderError as e:
        print(f"\nFAILED to construct provider: {e}")
        return 1
    print(f"\n-> using provider: {provider.name}")
    if provider.name == "mock":
        print("   NOTE: this is fake data. Set PNR_API_KEY to test a real provider.")

    _section("2. Raw provider response")
    try:
        raw = provider.fetch(pnr_number)
    except PNRProviderError as e:
        print(f"FAILED: {e}")
        return 1
    print(json.dumps(raw, indent=2, default=str))

    _section("3. Canonical fields the mapper will read")
    try:
        passenger = raw["Passangers"][0]
        print(f"TrainNumber   : {raw.get('TrainNumber')}")
        print(f"TrainName     : {raw.get('TrainName')}")
        print(f"JourneyClass  : {raw.get('JourneyClass')}")
        print(f"JourneyDate   : {raw.get('JourneyDate')}")
        print(f"ChatPrepared  : {raw.get('ChatPrepared')}")
        print(f"CurrentStatus : {passenger.get('CurrentStatus')}")
        print(f"BookingStatus : {passenger.get('BookingStatus')}")
    except (KeyError, IndexError) as e:
        print(f"FAILED: response is missing an expected field ({e}).")
        print("Adjust the adapter's _normalise() using the raw dump above.")
        return 1

    _section("4. Derived model features")
    try:
        mapped = map_pnr_response(raw)
    except UnsupportedPNRStatus as e:
        print(f"Not predictable: {e}")
        return 0
    except Exception as e:  # noqa: BLE001 - diagnostic tool, surface anything
        print(f"FAILED during mapping: {type(e).__name__}: {e}")
        return 1

    if mapped["resolved"]:
        print(f"Already resolved: {mapped['resolved_status']} (no prediction needed)")
        return 0

    print(json.dumps(mapped["features"], indent=2))
    print(f"\nEstimated (not looked up): {', '.join(mapped['estimated_fields'])}")

    _section("5. Prediction")
    try:
        from app.model import get_service

        service = get_service()
    except FileNotFoundError as e:
        print(f"No trained model: {e}")
        return 1

    probability = service.predict(mapped["features"])
    print(f"Confirmation probability: {probability:.1%}")
    for factor in service.top_factors(mapped["features"], probability):
        print(f"  - {factor['factor']}: {factor['impact']}")

    print("\nAll steps passed — this provider is wired up correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
