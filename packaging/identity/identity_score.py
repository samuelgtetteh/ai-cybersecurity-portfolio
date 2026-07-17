"""
Standalone scorer for the Hybrid Identity Anomaly Detector (Isolation Forest).

Replicates the exact 9-feature engineering used at serving time and scores a login event:
    hour, day_of_week, is_weekend, hourly_count, unique_pcs,
    logon_type_code, auth_type_code, orientation_code, success_code

Two features (hourly_count, unique_pcs) are rolling aggregates over a 1-hour sliding window per
user, so this scorer is STATEFUL: feed events in time order and the counts accumulate as a real
stream would. State is in-memory and resets on restart (a production deployment would back it with
Redis). The model + scaler live alongside this file.

Usage:
    from identity_score import score_event
    score_event({"src_user":"u1@DOM","src_pc":"PC1","auth_type":"Kerberos",
                 "logon_type":"Network","orientation":"LogOn","success":"Success"})
"""
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache

_HERE = os.path.dirname(os.path.abspath(__file__))

FEATURE_ORDER = ["hour", "day_of_week", "is_weekend", "hourly_count", "unique_pcs",
                 "logon_type_code", "auth_type_code", "orientation_code", "success_code"]

AUTH_TYPE_CODES = {
    "NTLM": 0, "?": 1, "Negotiate": 2, "Kerberos": 3,
    "MICROSOFT_AUTHENTICATION_PACKAGE_V1_0": 4, "MICROSOFT_AUTHENTICATION_PAC": 5,
    "MICROSOFT_AUTHENTICATION_PACKAGE": 6, "MICROSOFT_AUTHENTICATION_PACKAG": 7,
    "MICROSOFT_AUTHENTICATION_PACKAGE_V1": 8, "MICROSOFT_AUTHENTICATION_PACKAGE_": 9,
    "MICROSOFT_AUTHENTICATION_PA": 10,
}
LOGON_TYPE_CODES = {"Network": 0, "Service": 1, "Batch": 2, "?": 3, "Interactive": 4,
                    "NetworkCleartext": 5, "NewCredentials": 6, "Unlock": 7, "RemoteInteractive": 8}
ORIENTATION_CODES = {"LogOn": 0, "LogOff": 1, "TGS": 2, "AuthMap": 3, "TGT": 4}
SUCCESS_CODES = {"Success": 0, "Fail": 1}
UNKNOWN_CODE = -1
WINDOW = timedelta(hours=1)
_recent = defaultdict(deque)


@lru_cache(maxsize=1)
def _load():
    import joblib
    model = joblib.load(os.path.join(_HERE, "isolation_forest_model.pkl"))
    scaler = joblib.load(os.path.join(_HERE, "scaler.pkl"))
    return model, scaler


def score_event(event: dict) -> dict:
    """Score one login event. Returns {is_anomaly, anomaly_score, hourly_count, unique_pcs}.
    anomaly_score < 0 == anomalous (IsolationForest decision_function)."""
    import pandas as pd
    ts = event.get("timestamp")
    if ts is None:
        ts = datetime.now(timezone.utc)
    elif isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    user = event["src_user"]
    cutoff = ts - WINDOW
    dq = _recent[user]
    dq.append((ts, event.get("src_pc")))
    while dq and dq[0][0] < cutoff:
        dq.popleft()
    hourly_count = len(dq)
    unique_pcs = len({pc for _, pc in dq})

    row = {"hour": ts.hour, "day_of_week": ts.weekday(),
           "is_weekend": 1 if ts.weekday() in (5, 6) else 0,
           "hourly_count": hourly_count, "unique_pcs": unique_pcs,
           "logon_type_code": LOGON_TYPE_CODES.get(event.get("logon_type"), UNKNOWN_CODE),
           "auth_type_code": AUTH_TYPE_CODES.get(event.get("auth_type"), UNKNOWN_CODE),
           "orientation_code": ORIENTATION_CODES.get(event.get("orientation"), UNKNOWN_CODE),
           "success_code": SUCCESS_CODES.get(event.get("success"), UNKNOWN_CODE)}
    model, scaler = _load()
    scaled = scaler.transform(pd.DataFrame([row], columns=FEATURE_ORDER))
    score = float(model.decision_function(scaled)[0])
    return {"is_anomaly": score < 0, "anomaly_score": round(score, 6),
            "hourly_count": hourly_count, "unique_pcs": unique_pcs}


if __name__ == "__main__":
    import json
    print(json.dumps(score_event({"src_user": "demo@DOM", "src_pc": "PC1", "auth_type": "Kerberos",
                                  "logon_type": "Network", "orientation": "LogOn",
                                  "success": "Success"}), indent=2))
