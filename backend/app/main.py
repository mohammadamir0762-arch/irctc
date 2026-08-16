from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.model import get_service
from app.pnr_mapper import UnsupportedPNRStatus, map_pnr_response
from app.pnr_provider import PNRProviderError, get_provider
from app import storage

app = FastAPI(title="PNR Confirmation Predictor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PNRFeatures(BaseModel):
    """Manual/advanced input. Mirrors exactly the four inputs the real model
    was trained on — see app/train_real.py."""

    travel_class: str
    booking_position: int = Field(ge=0, le=2000)
    current_position: int = Field(ge=0, le=2000)
    days_before_journey: int = Field(ge=0, le=120)

    @field_validator("travel_class")
    @classmethod
    def _check_travel_class(cls, v):
        service = get_service()
        if v not in service.travel_classes:
            raise ValueError(f"travel_class must be one of {service.travel_classes}")
        return v


class Factor(BaseModel):
    factor: str
    impact: str


class PredictionResponse(BaseModel):
    probability: float
    confidence_label: str
    top_factors: list[Factor]


def _confidence_label(probability: float) -> str:
    """Thresholds are set from the real prediction distribution, not from
    round numbers. Waitlisted tickets confirm ~5% of the time overall and the
    model's 99th percentile output is ~0.26, so a 0.75 "likely" cutoff would
    label literally everything "unlikely" and tell the user nothing.

    Each band below is checked against real outcomes:
        >= 0.20  ->  36% actually confirmed  (top 2.6% of tickets)
        >= 0.10  ->  19% actually confirmed  (top 16%)
        >= 0.05  ->  12% actually confirmed  (top 38%)
        <  0.05  ->  under 5%
    """
    if probability >= 0.20:
        return "Good chance"
    if probability >= 0.10:
        return "Some chance"
    if probability >= 0.05:
        return "Unlikely"
    return "Very unlikely"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/options")
def options():
    service = get_service()
    return {"travel_class": service.travel_classes}


@app.get("/model")
def model_info():
    """What the model is and how well it actually performs, so the numbers
    it returns can be judged rather than taken on faith."""
    return get_service().metadata


@app.post("/predict", response_model=PredictionResponse)
def predict(features: PNRFeatures):
    try:
        service = get_service()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    payload = {
        "travel_class_code": service.class_code(features.travel_class),
        "booking_position": features.booking_position,
        "current_position": features.current_position,
        "days_before_journey": features.days_before_journey,
    }
    probability = service.predict(payload)
    factors = service.top_factors(payload, probability)

    return PredictionResponse(
        probability=round(probability, 4),
        confidence_label=_confidence_label(probability),
        top_factors=factors,
    )


@app.get("/pnr/{pnr_number}")
def check_pnr(pnr_number: str):
    if not pnr_number.isdigit() or len(pnr_number) != 10:
        raise HTTPException(status_code=400, detail="PNR number must be exactly 10 digits.")

    provider = get_provider()
    try:
        raw = provider.fetch(pnr_number)
    except PNRProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        mapped = map_pnr_response(raw)
    except UnsupportedPNRStatus as e:
        raise HTTPException(status_code=422, detail=str(e))

    if mapped["resolved"]:
        storage.log_check(pnr_number, is_mock=raw.get("_is_mock", False), resolved_status=mapped["resolved_status"])
        return {
            "pnr_number": pnr_number,
            "resolved": True,
            "status": mapped["resolved_status"],
            "is_mock": raw.get("_is_mock", False),
        }

    try:
        service = get_service()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    probability = service.predict(mapped["features"])
    factors = service.top_factors(mapped["features"], probability)

    storage.log_check(
        pnr_number,
        is_mock=mapped["is_mock"],
        journey_date=mapped["pnr_summary"]["journey_date_iso"],
        train_number=mapped["pnr_summary"]["train_number"],
        features=mapped["features"],
        context=mapped["context"],
        predicted_probability=probability,
    )

    return {
        "pnr_number": pnr_number,
        "resolved": False,
        "probability": round(probability, 4),
        "confidence_label": _confidence_label(probability),
        "top_factors": factors,
        "pnr_summary": mapped["pnr_summary"],
        "context": mapped["context"],
        "estimated_fields": mapped["estimated_fields"],
        "is_mock": mapped["is_mock"],
    }


@app.get("/flywheel/stats")
def flywheel_stats():
    """Visibility into the data flywheel: how many PNR checks have been
    logged, how many have a captured real outcome, and how many are real
    (non-mock) — i.e. how close this is to having a real training set."""
    return storage.stats()
