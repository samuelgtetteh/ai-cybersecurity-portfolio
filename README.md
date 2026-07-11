# Cybersecurity ML Research Portfolio
**Samuel Tetteh** · Independent Research · 2026

Three end-to-end machine learning prototypes covering compliance automation, identity threat detection, and industrial control system security. Each project uses publicly available datasets, open-source tools, and produces fully reproducible results. All three are also served live via a containerized API, and a fourth tool — Control Advisor — builds on top of them to turn environment scans into prioritized NIST 800-53 control recommendations.

---

## Results at a Glance

| Project | Dataset | Model | Key Metric |
|---------|---------|-------|------------|
| RegMap – Compliance Mapping | NIST SP 800-53 / HIPAA crosswalk (222 pairs) | Fine-tuned Sentence-BERT | Recall@5 = 0.735 on 34-query test set |
| Hybrid Identity Anomaly Detection | LANL Auth Logs (2M events) | Isolation Forest | 17,399 anomalies flagged (0.87%) |
| OT/ICS Intrusion Detection | HAI Turbine/Boiler Testbed (995K samples) | Deep Autoencoder | ROC AUC 0.929 (pooled) / 0.869 (session-disjoint) on 17,527 test attacks |

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
- **Live API:** `POST /identity/score` — scores one login event at a time, replacing the notebook's batch aggregates with live rolling counters (see [Path to Production](#path-to-production-live-api))
- **Saved Model:** `data/processed/isolation_forest_model_polars.pkl` (Polars notebook) / `isolation_forest_model.pkl` (live API — trained by an earlier pandas run whose notebook has since been removed; its saved model and categorical encodings are still what the live API depends on, see note below)
- **Exhibit:** `exhibits/Exhibit 12_hybrid _indentity.md.docx`

---

### 3. OT/ICS Intrusion Detection with Physics-Aware Autoencoder
**Research Pathway:** Intrusion detection for operational technology and critical infrastructure

A deep autoencoder trained exclusively on normal sensor and actuator readings from the HAI (Hardware-in-the-Loop Augmented ICS) turbine and boiler testbed. The model flags attacks by reconstruction error, with no labeled attack data required during training. Trained on 59 real sensor/actuator tags only — an earlier version inadvertently included the attack-label columns themselves as input features. That leak has been **quantified exactly** from the preserved leaked artifact: it scores a literally perfect ROC AUC 1.000000, and the contamination is model-deep (even its sensor-channel errors alone score AUC 1.0), so retraining without the leaked columns was the only fix.

A subsequent protocol audit (2026-07-10) found a second, subtler pitfall in the original pipeline: normal rows were pooled across **all four HAI files** before the train/validation split, so ~80% of test-file normal rows were seen in training. The model is therefore reported under both protocols — an "honesty ladder" where each step down is less flattering and more deployable:

| Metric | Value |
|--------|-------|
| Total samples | 995,400 |
| Sensor features | 59 |
| Model parameters | 36,059 |
| Leaked model (59 sensors + 4 label columns) | ROC AUC 1.000000 — a broken evaluation, not a strong model |
| **ROC AUC, leakage-free, pooled-normals protocol** | **0.929** (95% block-bootstrap CI 0.893–0.960; AP 0.733) |
| **ROC AUC, leakage-free, strict session-disjoint protocol** | **0.869** (AP 0.682) — the number a deployment should expect |
| Deployed threshold (MSE 0.009223) on canonical test files | recall 87.9%, precision 15.2%, FPR 20.1% |
| Balanced operating point (99th pct, MSE 0.060) | recall 72.6%, precision 42.4%, FPR 4.0% |
| Alarm aggregation (min-run k=10, default threshold) | 7,946 → 247 alert episodes (32×), 36/38 attack segments still caught |
| Baselines (canonical) | PCA-reconstruction AUC 0.854; Isolation Forest AUC 0.804 |

> Percentile thresholds calibrated on same-session normals overshoot their nominal false-positive rates by 2.1×–26× on the session-disjoint test files (and up to 53× for the strictly trained model) — threshold calibration, not ranking quality, is the operational bottleneck. Both pitfalls, the dual-protocol evaluation, and the calibration analysis are documented in the accompanying paper and reproducible via [`paper/ot_ics/eval_ot_ics.py`](paper/ot_ics/eval_ot_ics.py) + [`paper/ot_ics/eval_extras.py`](paper/ot_ics/eval_extras.py), mirrored in tracked notebooks [`05`](notebooks/05_ot_ics_paper_evaluation.ipynb) and [`05b`](notebooks/05b_ot_ics_extended_evaluation.ipynb).

- **Notebook:** [`notebooks/04_ot_ics_intrusion_detection.ipynb`](notebooks/04_ot_ics_intrusion_detection.ipynb)
- **Live API:** `POST /ics/score` — scores one sensor reading at a time; `GET /ics/example` returns a real normal reading to try it with (see [Path to Production](#path-to-production-live-api))
- **Saved Model:** `data/processed/autoencoder_hai.pth`
- **Exhibit:** `exhibits/Exhibit 13 OT ICS Intrusion Detection.docx`

---

### 4. Control Advisor – NIST 800-53 Control Recommendation Tool
**Research Pathway:** AI-assisted security control gap assessment

A CLI tool that scans an environment, has a natural-language conversation to understand context a scan can't infer (regulated data, sector, remote access posture, etc.), and produces a prioritized set of NIST SP 800-53 control recommendations with AI-drafted policy language — without the interview feeling like a rigid form.

- **Scanning:** local/WAN network device discovery (`scanner/network_scan.py`), plus cloud/IaC scanning (`scanner/cloud_scan.py`) against a real AWS account or a LocalStack-simulated one (see [`cloud-target-lab`](#related-repositories) below).
- **Interview:** free-text answers are interpreted by a small local LLM (Qwen2.5-1.5B-Instruct, via `scanner/llm_interview.py`) rather than requiring exact strings, with a deterministic glossary + confusion-detection fallback (`scanner/interview.py`) for terms the LLM can't reliably explain on its own.
- **Output:** DOCX and XLSX reports (`scanner/docx_report.py`, `scanner/xlsx_report.py`) with prioritized controls and AI-drafted policy language (`scanner/draft_language.py`), saved to a per-business-name report folder.
- **Run:** `python control-advisor/cli.py`
- **Code:** [`control-advisor/`](control-advisor/)

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
| Local LLM (Control Advisor) | Qwen2.5-1.5B-Instruct via `transformers`, `torch` |
| Reports (Control Advisor) | `python-docx`, `openpyxl` |
| Cloud Scanning (Control Advisor) | `boto3`, LocalStack |

---

## Repository Layout

```
notebooks/
  01_data_preparation.ipynb             NIST-HIPAA crosswalk cleaning (feeds RegMap)
  02_embedder_training_good.ipynb       RegMap Sentence-BERT training & eval
  03b_hybrid_identity_anomaly_polars.ipynb  LANL identity anomaly (Polars, 2M rows)
  04_ot_ics_intrusion_detection.ipynb   HAI autoencoder training & eval
  05_ot_ics_paper_evaluation.ipynb      OT/ICS rigorous eval (ROC/AUC, baselines, thresholds)
  05b_ot_ics_extended_evaluation.ipynb  OT/ICS leakage quantification, dual protocols, calibration, alarm filtering
  06_regmap_paper_evaluation.ipynb      RegMap retrieval eval (Recall@k/MRR/MAP + baselines, CIs)
  07_identity_redteam_evaluation.ipynb  Identity vs LANL red-team ground truth (AUC + baselines)

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

control-advisor/
  cli.py                                 Interactive CLI: scan, interview, generate reports
  scanner/
    network_scan.py                      Local/WAN network device discovery
    cloud_scan.py                        AWS/IaC scan (real account or LocalStack)
    environment_detect.py                Environment/context detection
    control_mapper.py                    Maps findings to NIST SP 800-53 controls
    interview.py, llm_interview.py       Natural-language adaptive interview (local LLM)
    docx_report.py, xlsx_report.py       DOCX/XLSX report generation
    draft_language.py                    AI-drafted policy language

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

## Related Repositories

Two supporting repos exist purely to give the live backend and Control Advisor something realistic to react to, since there's no production deployment or real cloud account behind either:

| Repo | Purpose |
|------|---------|
| [`cloud-target-lab`](https://github.com/samuelgtetteh/cloud-target-lab) | LocalStack-simulated AWS account for Control Advisor's cloud/IaC scan phase. |
| [`live-target-lab`](https://github.com/samuelgtetteh/live-target-lab) | Two standing Docker services that continuously generate synthetic login events and OT sensor telemetry and stream them to `/identity/score` and `/ics/score`, so both models can be observed against a continuous live-like source. |

See `docs/system_landscape.md` for the full map of how all the repos and containers fit together, and `docs/progress_log.md` for a dated changelog of recent work.

---

## Git Remotes

```bash
git push origin main   # → github.com/samuelgtetteh/ai-cybersecurity-portfolio
```

The two related repos above are pushed independently from their own directories (`cloud-target-lab/`, `live-target-lab/`), each with its own `git push origin main`.
