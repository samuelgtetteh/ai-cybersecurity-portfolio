"""
Live scoring endpoint for the Hybrid Identity Anomaly Detector (Isolation Forest).

The trained model (data/processed/isolation_forest_model.pkl + scaler.pkl) expects
9 features per login event, in this exact order (confirmed via scaler.feature_names_in_):
    hour, day_of_week, is_weekend, hourly_count, unique_pcs,
    logon_type_code, auth_type_code, orientation_code, success_code

Two of those were originally computed as whole-dataset batch aggregates (hourly_count,
unique_pcs) and the categorical codes were assigned by pd.factorize with no saved mapping.
Both are reconstructed here: category codes are recovered exactly from
data/processed/lanl_auth_with_anomalies.csv (which retains both the raw string and the
code it was assigned during training), and the aggregates are replaced with live rolling
counters that accumulate as real events stream in, in place of the original one-shot
whole-batch computation.
"""
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

import joblib
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/identity", tags=["identity"])

MODEL_PATH = Path("../data/processed/isolation_forest_model.pkl")
SCALER_PATH = Path("../data/processed/scaler.pkl")

model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)

FEATURE_ORDER = [
    "hour", "day_of_week", "is_weekend", "hourly_count", "unique_pcs",
    "logon_type_code", "auth_type_code", "orientation_code", "success_code",
]

AUTH_TYPE_CODES = {
    "NTLM": 0, "?": 1, "Negotiate": 2, "Kerberos": 3,
    "MICROSOFT_AUTHENTICATION_PACKAGE_V1_0": 4,
    "MICROSOFT_AUTHENTICATION_PAC": 5,
    "MICROSOFT_AUTHENTICATION_PACKAGE": 6,
    "MICROSOFT_AUTHENTICATION_PACKAG": 7,
    "MICROSOFT_AUTHENTICATION_PACKAGE_V1": 8,
    "MICROSOFT_AUTHENTICATION_PACKAGE_": 9,
    "MICROSOFT_AUTHENTICATION_PA": 10,
}
LOGON_TYPE_CODES = {
    "Network": 0, "Service": 1, "Batch": 2, "?": 3, "Interactive": 4,
    "NetworkCleartext": 5, "NewCredentials": 6, "Unlock": 7, "RemoteInteractive": 8,
}
ORIENTATION_CODES = {"LogOn": 0, "LogOff": 1, "TGS": 2, "AuthMap": 3, "TGT": 4}
SUCCESS_CODES = {"Success": 0, "Fail": 1}
UNKNOWN_CODE = -1

# In-memory rolling state — resets on restart. A production deployment would back this
# with Redis or similar so counts survive restarts and are shared across replicas.
_lock = Lock()
_hourly_counts: dict[tuple[str, int], int] = {}
_user_pcs: dict[str, set] = {}


class LoginEvent(BaseModel):
    src_user: str
    src_pc: str
    auth_type: str
    logon_type: str
    orientation: str
    success: str
    timestamp: Optional[datetime] = None


class AnomalyResult(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    hourly_count: int
    unique_pcs: int


@router.post("/score", response_model=AnomalyResult)
def score_event(event: LoginEvent) -> AnomalyResult:
    ts = event.timestamp or datetime.now(timezone.utc)
    hour = ts.hour
    day_of_week = ts.weekday()
    is_weekend = 1 if day_of_week in (5, 6) else 0

    with _lock:
        key = (event.src_user, hour)
        _hourly_counts[key] = _hourly_counts.get(key, 0) + 1
        hourly_count = _hourly_counts[key]

        pcs = _user_pcs.setdefault(event.src_user, set())
        pcs.add(event.src_pc)
        unique_pcs = len(pcs)

    row = {
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "hourly_count": hourly_count,
        "unique_pcs": unique_pcs,
        "logon_type_code": LOGON_TYPE_CODES.get(event.logon_type, UNKNOWN_CODE),
        "auth_type_code": AUTH_TYPE_CODES.get(event.auth_type, UNKNOWN_CODE),
        "orientation_code": ORIENTATION_CODES.get(event.orientation, UNKNOWN_CODE),
        "success_code": SUCCESS_CODES.get(event.success, UNKNOWN_CODE),
    }
    features_df = pd.DataFrame([row], columns=FEATURE_ORDER)

    scaled = scaler.transform(features_df)
    score = float(model.decision_function(scaled)[0])

    return AnomalyResult(
        is_anomaly=score < 0,
        anomaly_score=round(score, 6),
        hourly_count=hourly_count,
        unique_pcs=unique_pcs,
    )


@router.get("/health")
def health():
    return {"status": "ok"}
