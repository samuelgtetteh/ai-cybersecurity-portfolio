# Bookmark: "Run & configure the whole project from the browser"

**Status: NOT STARTED — bookmarked 2026-07-12 for a future session (usage-limit checkpoint).**
Build this after the alert case-management workflow (see `docs/decision_layer_plan.md`, section AQ) is committed.

## What the user asked for
> "Build a menu to help us configure many of the hard-coded limits we have in the app
> (e.g. how many records to keep). From the browser we should be able to run the compliance
> audit / get the background scanner working from within the webpage. In fact the complete
> project should be runnable from within the browser. The idea is building customisation into
> the project from the webpage."

Goal: turn the dashboard into a **control plane**, not just a monitor. Everything currently
done from the CLI / env vars / notebooks should be do-able from the browser.

## Scope (proposed phases)

### BC.1 — Settings menu (configure the hard-coded limits)
Expose the env-configured knobs as a live-editable settings panel. Current hard-coded/env values:
- **Retention (FIFO caps)** — `MAX_VERDICTS` (100000), `MAX_REQUESTS` (100000), `MAX_ACTIONS`
  (50000), `RETENTION_TRIM_EVERY` (100) in `backend/verdict_store.py`.
- **Policy thresholds** — `DECISION_WINDOW_SECONDS` (300), `IDENTITY_BURST_MIN` (3),
  `ICS_SUSTAINED_MIN` (3), `ICS_SEVERE_ERROR` (1.0), `IDENTITY_SEVERE` (-0.1),
  `DECISION_SUPPRESS_MIN` (3) in `backend/policy.py`.
- **AI triage** — `AI_TRIAGE_LLM` on/off, `LLM_SERVICE_URL`.
- **Regmap flag threshold** — the `top1 < 0.5` cutoff in `backend/app.py::map_control`.
Design notes:
- Backend: a `settings` store (new SQLite table `settings(key,value,updated_at)` or a JSON doc)
  read at runtime by `verdict_store`/`policy` instead of module-constants captured at import.
  IMPORTANT: those modules currently freeze env values at import time — refactor to read a
  live settings object (e.g. `settings.get("MAX_VERDICTS")`) so a change takes effect without a
  container restart. Keep env vars as the *default/seed*.
- Endpoints: `GET /decision/settings`, `PATCH /decision/settings` (validate ranges), and a
  "reset to defaults" action. Each change journalled (reuse the audit pattern).
- UI: a gear/settings drawer on the dashboard with grouped, validated fields + save + revert.
- Safety: clamp to sane ranges; never let a setting break scoring (advisory-only principle).

### BC.2 — Run the compliance audit / background scanner from the browser
- There is a background scanner / compliance-audit capability run outside the browser today
  (`backend/event_simulator.py`, the ICS/identity simulators, and the RegMap `/map` compliance
  mapping). Wire a **"Run audit / scan now"** button + status that triggers it server-side.
- Backend: a job runner — `POST /decision/scan` (kick off), `GET /decision/scan/{id}` (status),
  results streamed onto the existing SSE feed or a jobs panel. Long jobs run in a background
  task (FastAPI `BackgroundTasks` or an asyncio task) with progress persisted so the browser can
  poll/subscribe. Make it idempotent and cancelable.
- UI: a "Jobs / Scans" panel showing running/queued/finished scans with progress + last result.

### BC.3 — "Run the complete project from the browser"
The umbrella goal: a control panel that can start/stop the live monitors, trigger scans, adjust
config, manage suppressions/alerts (done in AQ), and view results — no terminal needed.
- Inventory every CLI/notebook/env entry point and give each a browser control:
  simulators (identity/ics), the live-target-lab feedback, retention enforce (already
  `POST /decision/retention/enforce`), reassess sweep (already `POST /decision/reassess`),
  model/embedder info, DB path/size, export/download the trail (CSV).
- Consider a lightweight auth gate before shipping browser-triggered actions that mutate state
  (even stubs) — the dashboard is currently unauthenticated.

## Precedence / dependencies
1. BC.1 first (settings refactor: module constants -> live settings store). Everything else is
   easier once config is centralized and runtime-readable.
2. BC.2 next (job runner pattern), reuses BC.1's settings + the SSE feed.
3. BC.3 last (fills in the remaining controls; add the auth gate here).

## Related
- `docs/decision_layer_plan.md` — the Record→Decide→Act→triage + AQ alert-workflow tracker.
- `docs/development_roadmap.md` — the broader post-submission roadmap.
- Dashboard: `backend/dashboard/index.html`. Endpoints: `backend/decision_api.py`.
- The advisory-only / never-break-scoring safety principle applies throughout.
