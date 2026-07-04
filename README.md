# Cybersecurity ML Research Portfolio
**Samuel Tetteh** · Independent Research · 2026

Three end-to-end machine learning prototypes covering compliance automation, identity threat detection, and industrial control system security. Each project uses publicly available datasets, open-source tools, and produces fully reproducible results.

---

## Results at a Glance

| Project | Dataset | Model | Key Metric |
|---------|---------|-------|------------|
| RegMap – Compliance Mapping | NIST SP 800-53 / HIPAA crosswalk (222 pairs) | Fine-tuned Sentence-BERT | Recall@5 = 0.74 on 34-query test set |
| Hybrid Identity Anomaly Detection | LANL Auth Logs (2M events) | Isolation Forest | 17,399 anomalies flagged (0.87%) |
| OT/ICS Intrusion Detection | HAI Turbine/Boiler Testbed (995K samples) | Deep Autoencoder | 84.3% attack recall on 18,303 attacks |

---

## Projects

### 1. RegMap – Automated Compliance Validation
**Research Pathway:** NLP-powered compliance automation (NIST → HIPAA mapping)

A fine-tuned Sentence-BERT model that retrieves the correct HIPAA Security Rule citation for any NIST SP 800-53 control. Trained on the official NIST-HIPAA crosswalk using `MultipleNegativesRankingLoss`, evaluated against a 60-provision corpus.

| Metric | Score |
|--------|-------|
| Recall@1 | 0.265 |
| Recall@3 | 0.559 |
| Recall@5 | **0.735** |
| MRR | 0.463 |
| Test queries | 34 (held-out) |
| Corpus size | 60 HIPAA provisions |

- **Notebook:** [`notebooks/02_embedder_training_good.ipynb`](notebooks/02_embedder_training_good.ipynb)
- **Live Demo:** [`demo/app.py`](demo/app.py) — run with `streamlit run demo/app.py`
- **Live API:** `POST /map` (see [Path to Production](#path-to-production-live-api) below)
- **Saved Model:** `models/regmap-embedder/`
- **Exhibit:** `exhibits/Exhibit11_RegMap_Project.docx`

---

### 2. Hybrid Identity Anomaly Detection
**Research Pathway:** Context-aware anomaly detection for hybrid identity systems

Unsupervised anomaly detection on 2 million authentication events from the LANL Comprehensive Cyber Security Events dataset. Uses Polars for memory-efficient processing and Isolation Forest to surface high-risk accounts — the same type of behavioral analysis needed in hybrid Azure AD / on-premises environments.

| Metric | Value |
|--------|-------|
| Events processed | 2,000,000 |
| Anomalies detected | 17,399 (0.87%) |
| Unique users | 7,399 |
| Unique source PCs | 4,157 |
| Top flagged account | ANONYMOUS LOGON@C586 (15,514 events) |
| Memory footprint | 150 MB (Polars) |

- **Notebook (Polars):** [`notebooks/03b_hybrid_identity_anomaly_polars.ipynb`](notebooks/03b_hybrid_identity_anomaly_polars.ipynb)
- **Notebook (pandas):** [`notebooks/03_hybrid_identity_anomaly.ipynb`](notebooks/03_hybrid_identity_anomaly.ipynb)
- **Live API:** `POST /identity/score` — scores one login event at a time, replacing the notebook's batch aggregates with live rolling counters (see [Path to Production](#path-to-production-live-api))
- **Saved Model:** `data/processed/isolation_forest_model_polars.pkl` (batch notebooks) / `isolation_forest_model.pkl` (live API — see note below)
- **Exhibit:** `exhibits/Exhibit 12_hybrid _indentity.md.docx`

---

### 3. OT/ICS Intrusion Detection with Physics-Aware Autoencoder
**Research Pathway:** Intrusion detection for operational technology and critical infrastructure

A deep autoencoder trained exclusively on normal sensor and actuator readings from the HAI (Hardware-in-the-Loop Augmented ICS) turbine and boiler testbed. The model detects attacks by flagging reconstruction errors above the 95th-percentile threshold — no labeled attack data required during training. Trained on 59 real sensor/actuator tags only (an earlier version of this model inadvertently included the attack-label columns themselves as input features; that data leak has since been fixed by excluding them, and the model was retrained — the numbers below reflect the corrected, leak-free result).

| Metric | Value |
|--------|-------|
| Total samples | 995,400 |
| Sensor features | 59 |
| Normal training samples | 781,677 |
| Attack samples (test) | 18,303 |
| Attack recall | **84.3%** |
| Attack precision | 0.61 |
| Detection threshold | 95th percentile of normal errors (MSE = 0.009223) |
| Model parameters | 36,059 |

- **Notebook:** [`notebooks/04_ot_ics_intrusion_detection.ipynb`](notebooks/04_ot_ics_intrusion_detection.ipynb)
- **Live API:** `POST /ics/score` — scores one sensor reading at a time; `GET /ics/example` returns a real normal reading to try it with (see [Path to Production](#path-to-production-live-api))
- **Saved Model:** `data/processed/autoencoder_hai.pth`
- **Exhibit:** `exhibits/Exhibit 13 OT ICS Intrusion Detection.docx`

---

## Path to Production: Live API

All three prototypes are also served from a single containerized FastAPI service (`backend/`), turning each research notebook into a callable, testable endpoint rather than a one-off script.

| Service | Endpoint | Description |
|---------|----------|--------------|
| RegMap | `POST /map` | NIST control text in → top-5 HIPAA citations + scores out |
| Identity Anomaly | `POST /identity/score` | One login event in → anomaly flag + score out |
| OT/ICS Intrusion Detection | `POST /ics/score` | One sensor reading in → anomaly flag + reconstruction error out |
| All three | `GET /health`, `GET /identity/health`, `GET /ics/health` | Liveness checks |
| — | `GET /docs` | Interactive Swagger UI for exploring/testing every endpoint |

**Run locally:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# then open http://localhost:8000/docs
```

**Run in Docker (fully reproducible, no local Python setup required):**
```bash
docker build -f backend/Dockerfile -t regmap-api .
docker run -p 8000:8000 regmap-api
```

**Simulating live traffic:** `backend/event_simulator.py` continuously sends sample NIST controls to `/map` and prints the compliance-check results, demonstrating how this would plug into a CI/CD pipeline:
```bash
python backend/event_simulator.py --api-url http://localhost:8000
```

**Adapting batch-trained models to live, one-at-a-time inference required a few explicit design decisions**, documented in code comments in `backend/identity_api.py` and `backend/ics_api.py`:
- The Identity Anomaly model's two batch-aggregate features (`hourly_count`, `unique_pcs`) are replaced with live rolling counters that accumulate as real events stream in, rather than being computed once over the whole historical dataset.
- The live API uses `isolation_forest_model.pkl` (the pandas-trained variant), not the Polars variant listed as the primary artifact above — only the pandas run's categorical encoding (auth type, logon type, etc.) could be exactly recovered from `data/processed/lanl_auth_with_anomalies.csv`, which retains both the raw category strings and the codes assigned to them at training time.
- The OT/ICS endpoint fills any sensor field missing from a request with a real recorded normal reading, not a per-feature statistical mean — the turbine/boiler operates in a few distinct regimes, so averaging each of the 59 sensors independently produces a combination that never actually occurs and reads as a false anomaly.

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.14 (notebooks) / 3.11 (Docker backend) |
| NLP / Embeddings | `sentence-transformers`, `transformers` |
| Deep Learning | PyTorch (`torch.nn`, `torch.optim`) |
| Classical ML | `scikit-learn` (IsolationForest, StandardScaler) |
| Data Processing | Polars 1.42, pandas |
| Visualization | matplotlib, seaborn |
| Web Demo | Streamlit |
| Live API | FastAPI, Uvicorn, Docker |
| Serialization | joblib, safetensors |

---

## Repository Layout

```
notebooks/
  02_embedder_training_good.ipynb       RegMap Sentence-BERT training & eval
  03_hybrid_identity_anomaly.ipynb      LANL identity anomaly (pandas)
  03b_hybrid_identity_anomaly_polars.ipynb  LANL identity anomaly (Polars, 2M rows)
  04_ot_ics_intrusion_detection.ipynb   HAI autoencoder training & eval

demo/
  app.py                                Streamlit demo for RegMap
  requirements.txt                      Demo dependencies

backend/
  app.py                                FastAPI service — mounts all three model APIs
  identity_api.py                       Identity Anomaly live-scoring router
  ics_api.py                            OT/ICS live-scoring router
  event_simulator.py                    Simulates live traffic against /map
  Dockerfile                            Builds the full three-model container
  requirements.txt                      Backend dependencies

models/
  regmap-embedder/                      Saved Sentence-BERT weights + eval results

data/
  raw/                                  Source datasets (not committed — large files)
  processed/                            Saved model artifacts and scored outputs

exhibits/
  Exhibit11_RegMap_Project.docx
  Exhibit 12_hybrid _indentity.md.docx
  Exhibit 13 OT ICS Intrusion Detection.docx
```

---

## Quickstart

```bash
# Install dependencies
pip install -r demo/requirements.txt

# Run the RegMap Streamlit demo
streamlit run demo/app.py
```

**Or run the full live API** (all three models — see [Path to Production](#path-to-production-live-api)):
```bash
docker build -f backend/Dockerfile -t regmap-api .
docker run -p 8000:8000 regmap-api
# then open http://localhost:8000/docs
```

To reproduce any notebook result, open the notebook in Jupyter and run **Kernel → Restart & Run All**. All data paths are relative (`../data/raw/`) and resolve correctly when run from the `notebooks/` directory.

---

## Git Remotes

```bash
git push origin main   # → github.com/samuelgtetteh/ai-cybersecurity-portfolio
```
