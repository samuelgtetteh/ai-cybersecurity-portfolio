"""
Standalone scorer for the OT/ICS Intrusion Detector (autoencoder on HAI sensor data).

Loads the trained autoencoder + scaler + metadata (input_dim / encoding_dim / threshold / the 59
sensor feature order) that sit alongside this file, computes the reconstruction error for a sensor
reading, and flags it as an intrusion if the error exceeds the trained threshold. Missing sensor
fields are filled from a real recorded normal reading (BASELINE_READING).

Usage:
    from otics_score import score_reading, BASELINE_READING
    score_reading(BASELINE_READING)                 # normal -> is_anomaly False
    score_reading({"P1_B2004": 5.0})                # tampered -> likely anomaly
"""
import ast
import os
from functools import lru_cache

_HERE = os.path.dirname(os.path.abspath(__file__))


def _meta():
    m = {}
    for line in open(os.path.join(_HERE, "autoencoder_hai_meta.txt"), encoding="utf-8"):
        k, _, v = line.partition("=")
        m[k] = v.strip()
    return m


_M = _meta()
INPUT_DIM = int(_M["input_dim"])
ENCODING_DIM = int(_M["encoding_dim"])
THRESHOLD = float(_M["threshold"])
FEATURE_ORDER = ast.literal_eval(_M["feature_cols"])

# A real observed normal reading (train1.csv row 1000, attack=0), used to fill any field missing
# from a request — an all-means vector is NOT physically realistic and scores as anomalous.
BASELINE_READING = {
    "P1_B2004": 0.0983, "P1_B2016": 0.9481, "P1_B3004": 399.2321, "P1_B3005": 1110.3986,
    "P1_B4002": 32.0, "P1_B4005": 0.0, "P1_B400B": 32.9705, "P1_B4022": 35.3325,
    "P1_FCV01D": 0.0, "P1_FCV01Z": 0.2838, "P1_FCV02D": 100.0, "P1_FCV02Z": 95.5368,
    "P1_FCV03D": 53.7863, "P1_FCV03Z": 54.3228, "P1_FT01": 115.6234, "P1_FT01Z": 579.1716,
    "P1_FT02": 6.1417, "P1_FT02Z": 31.9776, "P1_FT03": 310.936, "P1_FT03Z": 1111.5228,
    "P1_LCV01D": 21.9717, "P1_LCV01Z": 21.7834, "P1_LIT01": 395.0419, "P1_PCV01D": 30.7836,
    "P1_PCV01Z": 31.4728, "P1_PCV02D": 12.0, "P1_PCV02Z": 12.0102, "P1_PIT01": 0.8943,
    "P1_PIT02": 0.2153, "P1_TIT01": 35.8032, "P1_TIT02": 37.146, "P2_24Vdc": 28.0246,
    "P2_Auto": 1.0, "P2_Emgy": 0.0, "P2_On": 1.0, "P2_SD01": 20.0, "P2_SIT01": 814.0,
    "P2_TripEx": 0.0, "P2_VT01e": 11.8639, "P2_VXT02": -3.2829, "P2_VXT03": -1.2577,
    "P2_VYT02": 0.4135, "P2_VYT03": 1.8313, "P3_LCP01D": 4.0, "P3_LCV01D": 0.0,
    "P3_LH": 70.0, "P3_LL": 10.0, "P3_LT01": 68.95255, "P4_HT_FD": -0.0001,
    "P4_HT_LD": -0.0072, "P4_HT_PO": 0.0724, "P4_HT_PS": 0.0, "P4_LD": 300.9802,
    "P4_ST_FD": -0.003, "P4_ST_LD": 298.0324, "P4_ST_PO": 287.1274, "P4_ST_PS": 50.9871,
    "P4_ST_PT01": 9916.0, "P4_ST_TT01": 27627.0,
}


def _build_autoencoder():
    import torch.nn as nn

    class Autoencoder(nn.Module):
        def __init__(self, input_dim, encoding_dim=32):
            super().__init__()
            self.encoder = nn.Sequential(nn.Linear(input_dim, 128), nn.ReLU(),
                                         nn.Linear(128, 64), nn.ReLU(),
                                         nn.Linear(64, encoding_dim))
            self.decoder = nn.Sequential(nn.Linear(encoding_dim, 64), nn.ReLU(),
                                         nn.Linear(64, 128), nn.ReLU(),
                                         nn.Linear(128, input_dim))

        def forward(self, x):
            return self.decoder(self.encoder(x))

    return Autoencoder


@lru_cache(maxsize=1)
def _load():
    import joblib
    import torch
    scaler = joblib.load(os.path.join(_HERE, "scaler_hai.pkl"))
    model = _build_autoencoder()(INPUT_DIM, ENCODING_DIM)
    model.load_state_dict(torch.load(os.path.join(_HERE, "autoencoder_hai.pth"), map_location="cpu"))
    model.eval()
    return model, scaler


def score_reading(readings: dict) -> dict:
    """Score a sensor reading (dict of tag->value). Returns
    {is_anomaly, reconstruction_error, threshold, missing_fields}."""
    import torch
    model, scaler = _load()
    missing = [f for f in FEATURE_ORDER if f not in readings]
    row = [readings.get(f, BASELINE_READING[f]) for f in FEATURE_ORDER]
    scaled = scaler.transform([row])
    with torch.no_grad():
        x = torch.tensor(scaled, dtype=torch.float32)
        error = torch.mean((model(x) - x) ** 2).item()
    return {"is_anomaly": error > THRESHOLD, "reconstruction_error": round(error, 6),
            "threshold": THRESHOLD, "missing_fields": missing}


if __name__ == "__main__":
    import json
    print("normal:", json.dumps(score_reading(BASELINE_READING)))
    tampered = dict(BASELINE_READING); tampered["P1_B2004"] = 8.0; tampered["P1_FT01"] = 900.0
    print("tampered:", json.dumps(score_reading(tampered)))
