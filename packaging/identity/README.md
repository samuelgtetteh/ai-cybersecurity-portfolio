---
license: apache-2.0
tags:
- anomaly-detection
- cybersecurity
- identity
- insider-threat
- isolation-forest
---

# Hybrid Identity Anomaly Detector

An **Isolation Forest** model that flags anomalous authentication events — the patterns behind
credential compromise, lateral movement, and insider threats — across a hybrid (cloud + on-prem)
identity environment. Trained and evaluated on the LANL authentication dataset (~2M events).

## What it does
Scores each login event and returns an anomaly score (negative = anomalous). It uses 9 features:
time (hour / day-of-week / weekend), a per-user **1-hour rolling** login count and distinct-machine
count, and encoded logon type / auth type / orientation / success. The two rolling features make the
scorer **stateful** — feed events in time order and it behaves like a live stream.

## Quick start
```bash
pip install -r requirements.txt
python example.py
```
```python
from identity_score import score_event
score_event({"src_user":"u1@DOM","src_pc":"PC1","auth_type":"Kerberos",
             "logon_type":"Network","orientation":"LogOn","success":"Success"})
# -> {"is_anomaly": false, "anomaly_score": ..., "hourly_count": 1, "unique_pcs": 1}
```

## Serving API (Docker)
```bash
docker run -p 8081:8080 ghcr.io/samuelgtetteh/identity-anomaly:0.1
curl -s localhost:8081/score -H 'Content-Type: application/json' \
  -d '{"src_user":"u1@DOM","src_pc":"PC1","auth_type":"Kerberos","logon_type":"Network","orientation":"LogOn","success":"Success"}'
```

## Files
- `isolation_forest_model.pkl` — the trained model · `scaler.pkl` — the fitted StandardScaler
- `identity_score.py` — feature engineering + scoring · `serve.py` — FastAPI wrapper

## Intended use & limitations
Assistive detection for a SOC: it surfaces events worth investigating, not a verdict. Anomaly ≠
malicious — a human should triage flagged events. Feature encodings and rolling-window semantics
match the training/serving pipeline; scores are only comparable within the same deployment.

## Data & license
Trained on the LANL "Comprehensive, Multi-Source Cyber-Security Events" dataset (subject to LANL's
terms). Code and released weights: Apache-2.0 (`LICENSE`).

## Citation
Tetteh, S. G. *Hybrid Identity Anomaly Detection.* Jarvis College of Computing and Digital Media,
DePaul University.
