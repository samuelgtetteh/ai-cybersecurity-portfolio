# Decision Layer → AI Platform — build plan & checkpoint

Implements Track C (real-time Record → Decide → Act decisioning layer) and Track E
(LLM/agentic platform) from `docs/development_roadmap.md`. This is the build the user
chose to start first. It turns the current stateless RedMap scorer into an operational
decisioning system, and becomes the basis for a new **Exhibit 16**. Started 2026-07-11.

## Why this is unblocked now
Per the roadmap dependency analysis, Track C depends only on the existing containerized
system (done) — it needs nothing from the research track. Track E (AI layer) sits on top
of C. Existing assets that make E cheap: the local **Qwen2.5-1.5B-Instruct** model
(`models/qwen2.5-1.5b-instruct`, already used by Control Advisor) and the fine-tuned
**RegMap embedder** (`models/regmap-embedder`) for RAG.

## Current backend (starting point)
`backend/app.py` mounts `/map` (RegMap retrieval) + routers `/identity/score`
(Isolation Forest) and `/ics/score` (autoencoder). Each returns a structured verdict but
**persists nothing** (Exhibit 14 §3: "stateless scorer"). All three verdicts are the raw
material the decision layer records and acts on.

## Architecture (from Exhibit 14 §9: Record → Decide → Act)
- **Record** — every verdict is written to a durable store (append-only trail),
  independent of any test client.
- **Decide** — a policy layer evaluates recorded verdicts against rules (e.g. any anomaly;
  repeated anomalies from one subject within a window; low-confidence compliance mapping).
- **Act** — a decision triggers a response (alert, ticket, webhook, page). Start with
  logged/stubbed actions + a webhook.
- Arrangement: inline first (simplest), with a clean seam to move to a decoupled
  stream-consumer later (the more production-grade pattern noted in Exhibit 14 §9).
- **AI layer (Track E)** — LLM-assisted triage of the anomaly queue (Qwen) + RAG over
  regulatory text (RegMap embedder) to explain/contextualize each decision.

## Phases & progress
- [x] **C1 — Record + production logging/feedback.** (DONE 2026-07-11) `backend/verdict_store.py`
  (stdlib SQLite, thread-safe). Two tables: `verdicts` (model decision + request metadata +
  ground_truth) and `requests` (audit of non-scored traffic). `record_verdict_safe(...)` wired into
  `/identity/score` (subject=src_user), `/ics/score`, `/map` (flag top-1 sim < 0.5); each stashes
  `request.state.verdict_id`.
  - **App middleware** (`app.py`) logs EVERY request: enriches the verdict row with
    latency/status/client/path and returns `X-Verdict-Id` header; audits non-scored requests.
  - **Feedback loop** (production-decoupled): `POST /decision/verdicts/{id}/feedback {ground_truth}`
    (synonyms normalized to malicious/benign) — any live client (analyst/SOAR/ticket/simulator) labels
    a decision by its X-Verdict-Id. `GET /decision/metrics` computes precision/recall/specificity from
    the DB (persists the Exhibit 14 tally). Also `GET /decision/verdicts` (filters incl. labeled),
    `GET /decision/requests`, `GET /decision/stats`.
  - Verified end-to-end via TestClient (header → feedback → metrics → audit; 422 bad label, 404 missing
    id). Reproducible: `notebooks/08_decision_layer_record.ipynb` (executed). `.gitignore` updated to
    exclude `data/*.db*` (runtime trail, not source). DB path via `$VERDICT_DB`, default `data/verdicts.db`.
  - **Live-lab feedback wiring — DONE 2026-07-11** (separate repo `C:\Users\User\live-target-lab`):
    `identity_generator.py` and `ics_generator.py` now read `X-Verdict-Id` from each `/score` response
    and POST their known injected label to `/decision/verdicts/{id}/feedback` (best-effort, `FEEDBACK`
    env toggle; README updated). Verified end-to-end by routing the real generator code through the
    backend TestClient — all verdicts auto-labelled, `/decision/metrics` populated. **Not yet committed/
    pushed in that repo, and the container must be rebuilt (`docker compose up -d --build`) to take
    effect on the running live-lab.**
- [ ] **C2 — Decide.** `backend/policy.py`: rule set over the trail (per-subject windowed
  anomaly counts, severity). `GET /decision/alerts` (derived decisions). Configurable rules.
- [ ] **C3 — Act.** `backend/actions.py`: pluggable responders (log, webhook, ticket stub),
  dispatched when a decision fires; actions themselves recorded for audit.
- [ ] **E — AI platform.** LLM triage summary per alert (Qwen, local) + RAG over regulation
  corpus (RegMap embedder) to attach the relevant control/obligation context to a decision.
- [ ] **Exhibit 16** — document the running decisioning system with measured evidence,
  mirroring the Exhibit 14 style.

## Design decisions
- SQLite via stdlib (no new heavy dep); path from env `VERDICT_DB`, default
  `data/verdicts.db`. A production note (Redis/Postgres, decoupled stream) is documented,
  not implemented — same honest-scope framing as the rest of the portfolio.
- Recording must not change scoring behaviour or break the live-validation tests
  (Exhibit 14): it is additive and side-effecting only.

## Resume pointer
**Last done:** C1 (Record) + production logging/feedback loop complete & verified end-to-end
(2026-07-11); notebook 08 executed. Backend now logs every request, returns X-Verdict-Id, accepts
ground-truth feedback, and computes live precision/recall from the DB.
SWaT dataset verified & acquired (106 MB zip, `data/raw/SWaT Dataset Secure Water Treatment
System.zip`; normal/attack/merged CSVs, 51 tags + Normal/Attack label; official iTrust
request also submitted for citable provenance).
**Next:** implement **C2 (Decide)** — `backend/policy.py` with per-subject windowed rules over
the recorded trail (start: N flagged identity verdicts from one subject within a window →
a derived alert), plus `GET /decision/alerts`. Then C3 (Act), then E (AI layer: Qwen triage +
RegMap-embedder RAG). Notebooks as needed per phase. Related: [[development-roadmap-status]].
