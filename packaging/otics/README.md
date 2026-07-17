---
license: apache-2.0
tags:
- anomaly-detection
- cybersecurity
- ot-security
- ics
- scada
- autoencoder
---

# OT/ICS Intrusion Detector (Autoencoder)

A deep **autoencoder** that detects cyber-physical attacks on industrial control systems from
sensor/actuator telemetry. Trained on the **HAI** (HIL-based Augmented ICS) turbine/boiler testbed
using **only normal operation** — so it needs no labeled attacks — and flags a reading as an
intrusion when its **reconstruction error** exceeds a learned threshold.

## What it does
Takes a reading of the 59 real HAI sensor/actuator tags, reconstructs it, and compares the
reconstruction error to the trained threshold (`0.009223`). Missing tags are filled from a real
recorded normal reading, so partial live feeds still score sensibly.

- Architecture: 59 → 128 → 64 → **32** (encoding) → 64 → 128 → 59, ReLU
- Detection: reconstruction MSE > threshold ⇒ anomaly

## Quick start
```bash
pip install -r requirements.txt
python example.py
```
```python
from otics_score import score_reading, BASELINE_READING
score_reading(BASELINE_READING)                 # normal -> is_anomaly False
score_reading({**BASELINE_READING, "P1_FT01": 900.0})   # tampered -> anomaly
```

## Serving API (Docker)
```bash
docker run -p 8082:8080 ghcr.io/samuelgtetteh/otics-anomaly:0.1
curl -s localhost:8082/example | curl -s localhost:8082/score -H 'Content-Type: application/json' -d @-  # (or POST {"readings": {...}})
```
`GET /example` returns a real normal reading; `POST /score {"readings": {...}}` scores one.

## Files
- `autoencoder_hai.pth` — trained weights · `scaler_hai.pkl` — fitted StandardScaler
- `autoencoder_hai_meta.txt` — input_dim / encoding_dim / threshold / 59 feature order
- `otics_score.py` — model + scoring · `serve.py` — FastAPI wrapper

## Intended use & limitations
Assistive monitoring for OT/ICS: a high reconstruction error flags a reading worth investigating,
not a confirmed attack. The threshold is tuned to this HAI testbed; deploying on a different plant
requires re-fitting the scaler/threshold on that plant's normal data. Trained on 59 specific HAI
tags — inputs must use those tag names.

## Data & license
Trained on the HAI dataset (iTrust/HIL testbed; subject to its terms). Code and released weights:
Apache-2.0 (`LICENSE`).

## Citation
Tetteh, S. G. *OT/ICS Intrusion Detection with a Physics-Aware Autoencoder.* Jarvis College of
Computing and Digital Media, DePaul University.
