# Cybersecurity ML Research Portfolio
**Samuel Tetteh** · Independent Research · 2026

Three end-to-end machine learning prototypes covering compliance automation, identity threat detection, and industrial control system security. Each project uses publicly available datasets, open-source tools, and produces fully reproducible results.

---

## Results at a Glance

| Project | Dataset | Model | Key Metric |
|---------|---------|-------|------------|
| RegMap – Compliance Mapping | NIST SP 800-53 / HIPAA crosswalk (222 pairs) | Fine-tuned Sentence-BERT | Recall@5 = 0.74 on 34-query test set |
| Hybrid Identity Anomaly Detection | LANL Auth Logs (2M events) | Isolation Forest | 17,399 anomalies flagged (0.87%) |
| OT/ICS Intrusion Detection | HAI Turbine/Boiler Testbed (995K samples) | Deep Autoencoder | 100% attack recall on 18,303 attacks |

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
- **Saved Model:** `data/processed/isolation_forest_model_polars.pkl`
- **Exhibit:** `exhibits/Exhibit 12_hybrid _indentity.md.docx`

---

### 3. OT/ICS Intrusion Detection with Physics-Aware Autoencoder
**Research Pathway:** Intrusion detection for operational technology and critical infrastructure

A deep autoencoder trained exclusively on normal sensor and actuator readings from the HAI (Hardware-in-the-Loop Augmented ICS) turbine and boiler testbed. The model detects attacks by flagging reconstruction errors above the 95th-percentile threshold — no labeled attack data required during training.

| Metric | Value |
|--------|-------|
| Total samples | 995,400 |
| Sensor features | 63 |
| Normal training samples | 781,677 |
| Attack samples (test) | 18,303 |
| Attack recall | **100%** |
| Detection threshold | 95th percentile of normal errors |
| Model parameters | 37,087 |

- **Notebook:** [`notebooks/04_ot_ics_intrusion_detection.ipynb`](notebooks/04_ot_ics_intrusion_detection.ipynb)
- **Saved Model:** `data/processed/autoencoder_hai.pth`
- **Exhibit:** `exhibits/Exhibit 13 OT ICS Intrusion Detection.docx`

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.14 |
| NLP / Embeddings | `sentence-transformers`, `transformers` |
| Deep Learning | PyTorch (`torch.nn`, `torch.optim`) |
| Classical ML | `scikit-learn` (IsolationForest, StandardScaler) |
| Data Processing | Polars 1.42, pandas |
| Visualization | matplotlib, seaborn |
| Web Demo | Streamlit |
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

To reproduce any notebook result, open the notebook in Jupyter and run **Kernel → Restart & Run All**. All data paths are relative (`../data/raw/`) and resolve correctly when run from the `notebooks/` directory.

---

## Git Remotes

```bash
git push origin main   # → github.com/samuelgtetteh/ai-cybersecurity-portfolio
```
