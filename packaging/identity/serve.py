"""Minimal serving API for the Hybrid Identity Anomaly Detector (used by the Docker image).

POST /score {"src_user","src_pc","auth_type","logon_type","orientation","success","timestamp"?}
  -> {is_anomaly, anomaly_score, hourly_count, unique_pcs}
GET  /health
"""
import os
import sys
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from identity_score import score_event  # noqa: E402

app = FastAPI(title="Hybrid Identity Anomaly Detector")


class LoginEvent(BaseModel):
    src_user: str
    src_pc: str
    auth_type: str
    logon_type: str
    orientation: str
    success: str
    timestamp: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score")
def score(e: LoginEvent):
    return score_event(e.model_dump())
