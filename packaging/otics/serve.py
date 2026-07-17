"""Minimal serving API for the OT/ICS Intrusion Detector (used by the Docker image).

POST /score {"readings": {tag: value, ...}} -> {is_anomaly, reconstruction_error, threshold, missing_fields}
GET  /example  -> a real normal reading you can POST as-is
GET  /health
"""
import os
import sys
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from otics_score import score_reading, BASELINE_READING  # noqa: E402

app = FastAPI(title="OT/ICS Intrusion Detector")


class SensorReading(BaseModel):
    readings: Dict[str, float]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/example")
def example():
    return BASELINE_READING


@app.post("/score")
def score(payload: SensorReading):
    return score_reading(payload.readings)
