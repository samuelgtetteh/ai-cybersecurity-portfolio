# Project Roadmap

Phase-wise progression plan for the portfolio, agreed as the plan of record.
Planning document only — no phase is implemented until explicitly started.
Ordered so evaluation rigor comes first (strengthens every exhibit), then the
real-time response capability, then packaging.

```
Phase 0 (prep) ──► Phase 1 (rigor) ──► Phase 3 (packaging)
                        │                     ▲
                        └──► Phase 2 (response) ┘
Phase 4 ── runs in parallel, anytime
```

---

## Phase 0 — Clean baseline (prerequisite, small)
Everything below assumes a committed starting point.
- Commit outstanding work: identity-generator behavioural-attack fix (`live-target-lab`), `docs/logs/tally_detection.py`, Exhibit 14.
- Reproducibility: commit the one evidence snapshot behind Exhibit 14's numbers (`docs/logs/2026-07-05_120350/`), which is otherwise gitignored.
- Remove the stray `awesome_wright` container.
- **Done when:** clean `git status` across all repos; exhibit numbers reproducible from committed data.

---

## Phase 1 — Scientific Credibility & Evaluation Rigor  (start here)
**Objective:** move each model from "it works" to "rigorously evaluated," with metrics an expert reviewer would accept.

- **OT/ICS (biggest payoff):** HAI ships attack labels → fully supervised. ROC + PR curves, AUC/AP; **threshold justification** (curve of recall/precision/FP-rate vs. threshold, replacing the hand-picked 95th percentile); per-attack-type breakdown; error analysis.
- **Identity Anomaly:** unsupervised → the unlock is labels. Check whether the LANL copy includes red-team ground truth (`redteam.txt`); if so, evaluate the Isolation Forest against real compromise events → real ROC/AUC/PR (biggest credibility win available). Otherwise, formalize the synthetic behavioural-burst attacks into a labelled test set.
- **RegMap:** add rigor cheaply — baseline comparison (fine-tuned Sentence-BERT vs. off-the-shelf vs. keyword/BM25); bootstrap confidence intervals on the 34-query test set; error analysis of misses.
- **Cross-cutting:** fixed seeds, documented splits, confidence intervals, short methodology writeup.

**Deliverables:** an evaluation notebook per model producing curves + tables; publication-style figures; a rigor section added to Exhibits 11–13 (or a new Evaluation & Benchmarking exhibit).
**Done when:** every model has curves, an AUC/AP number, a baseline comparison, and a quantitatively justified threshold.

---

## Phase 2 — Real-Time Decisioning Layer
**Objective:** turn detection into autonomous response — realize Exhibit 14 §9.
**Locked design:** Hybrid architecture · TimescaleDB/Postgres single store · Grafana dashboard. See `docs/phase2_plan.md` for the detailed build plan.

- **2a Record** — RedMap writes every verdict to Postgres.
- **2b Decide** — decision-service applies config-driven windowed rules.
- **2c Act** — alert log + webhook (+ optional simulated autonomous response).
- **2d See** — Grafana dashboards over Postgres (rates + live alerts table).

**Deliverables:** verdict persistence + decision-service + Grafana; new evidence → **Exhibit 15: Operational Response**.
**Done when:** an injected attack flows end-to-end — persisted verdict → fired alert → dashboard update — demonstrably and on screen.

---

## Phase 3 — Petition Packaging & Narrative Coherence
**Objective:** consolidate all technical work into a submission-ready petition. Consumes outputs of Phases 1–2.
- Consistency audit: every number/claim matches across personal statement, README, notebooks, and all exhibits.
- Prong mapping: each exhibit tied to a proposed-endeavor pathway and to the three NIW prongs.
- Fold in Phase 1 evaluation figures and Phase 2 response evidence.
- Master portfolio-index exhibit; verify every claim has backing evidence and every exhibit is referenced.

**Deliverables:** submission-ready exhibit set + a claim→evidence consistency matrix.
**Done when:** a reviewer can trace every claim to evidence with no contradictory numbers.

---

## Phase 4 — Productionization & Maintenance (parallelizable, lower priority)
**Objective:** engineering-maturity signals.
- Shrink the backend image (CPU-only torch → ~1–2 GB from 8.8 GB).
- CI: GitHub Actions running the pytest suite + `ruff` on push.
- Basic auth / rate-limiting on the API; model-version metadata endpoint.
- **Done when:** green CI, slim reproducible deploy.
