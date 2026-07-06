# Progress Log

Dated entries of what changed each working session, so a new day can start by
reading the latest entry instead of reconstructing context from scratch.
Newest entry at the top.

## 2026-07-05

**Real-time decisioning plan, three scientific papers, and OT/ICS number corrections.**

Planning (committed):
- `docs/roadmap.md` — full phased plan (Phase 0 baseline → Phase 1 evaluation
  rigor → Phase 2 real-time decisioning → Phase 3 packaging → Phase 4 prod).
  Scope decision recorded: **a separate scientific paper per model** (not one
  integrated paper). arXiv baseline; Computers & Security / USENIX CSET /
  IEEE Access / MDPI as candidate venues (submit to one at a time).
- `docs/phase2_plan.md` — detailed real-time decisioning design, locked as
  **Hybrid architecture + TimescaleDB/Postgres single store + Grafana** (not yet
  built; Phase 2).

Scientific papers (drafts are LOCAL in `paper/` — that folder is gitignored per
request; this log is the referenceable record of what was done):
- `paper/ot_ics/` — "Label Leakage in ICS Anomaly Detection … HAI Testbed."
  Rigorous eval via `eval_ot_ics.py` on the canonical HAI test files
  (test1+test2, 444,600 samples, 17,527 attacks): **ROC AUC 0.929**, AP 0.733;
  beats PCA-recon (0.854) and Isolation Forest (0.804). Threshold-sensitivity,
  per-process breakdown, point-wise + point-adjusted metrics. 7 rendered
  equations; 27 verified references; 5-part Related Work; generalization-gap
  discussion (random split 5% FPR vs. session-disjoint test files 20% FPR).
- `paper/regmap/` — "Automated Regulatory Crosswalking … NIST 800-53 → HIPAA."
  Rigorous eval via `eval_regmap.py`: fine-tuning lifts Recall@5 0.500 → **0.735**
  and beats BM25 (0.353) and TF-IDF (0.500), bootstrap 95% CIs. 5 equations;
  25 verified references; 4-part Related Work.
- `paper/identity/` — "Access Breadth over Ensembles: A Red-Team Evaluation …
  LANL." Required acquiring the raw `auth.txt.gz` (7.6 GB) + `redteam.txt.gz`
  (the processed slices are day-1 only and predate red-team activity). Window
  [150000, 500000] extracted to `data/raw/auth_window.csv` (61.5M rows, 46
  red-team logins); `eval_identity.py` fits an Isolation Forest on the window's
  normal events and scores against red-team labels. Result: **AUC 0.803**
  (CI 0.786–0.819); central finding — **access breadth (unique_pcs) alone AUC
  0.905** beats the full ensemble; login volume is below chance. Paper reframed
  around this: 4 equations, 4-part Related Work, 25 verified references.
  All three papers are now drafted (local in `paper/`).

Citations: all foundational references verified against primary sources this
session (arXiv / ACM DL / IEEE / USENIX / Springer / ACL & IR anthologies).

Corrections (committed):
- **OT/ICS numbers in README + Exhibit 13** reconciled. Finding: the old
  "84.3% recall, 0.61 precision, 95th percentile" are NOT wrong — they are a
  valid *random train/test split* result (confirmed from the classification-report
  images: recall 15433/18303=0.843, precision 15433/25204=0.612). They differ
  from the canonical test-file eval (AUC 0.929, ~20% FPR) due to cross-session
  distribution shift. README now presents BOTH protocols and leads with AUC 0.929;
  Exhibit 13 gained a §4.3 rigorous re-evaluation and clarified captions.
- `train2.csv` actually contains 776 attack rows (so the 18,303 total = 776 +
  11,538 + 5,989); canonical test = test1+test2 = 17,527 attacks.

Reproducible notebooks (tracked, on GitHub, with metrics + figures embedded):
- `notebooks/05_ot_ics_paper_evaluation.ipynb`
- `notebooks/06_regmap_paper_evaluation.ipynb`
- `notebooks/07_identity_redteam_evaluation.ipynb`

Identity red-team result (notebook 07): context-aware Isolation Forest **AUC 0.803**
(95% CI 0.786–0.819) on 48 real red-team logins; notable honest finding — the
single feature `unique_pcs` (distinct machines per account) alone scores **AUC
0.905**, out-performing the full model, because lateral movement is strongly
signalled by access breadth. The Identity paper is being reframed around this.

Reproduce a paper's numbers: run the corresponding notebook (05/06/07), or
`python paper/<name>/eval_*.py` then `python paper/<name>/build_paper.py`.

## 2026-07-04

**Live test environment for Identity Anomaly and OT/ICS, end to end.**

- Diagnosed and fixed a bug in `live-target-lab/identity_generator.py`: its
  "suspicious" auth types (`"?"`, `"MICROSOFT_AUTHENTICATION_PACKAGE_V1_0"`)
  were actually common, known values in the training data, so they barely
  moved the anomaly score. Confirmed via direct curl testing against the live
  API that only genuinely unrecognized auth strings (which map to the
  model's unseen/unknown code) trigger a real alert. Replaced them with
  `TotallyUnrecognizedAuth`, `LegacyProtocolXYZ`, `UnverifiedCustomAuth`.
- Rebuilt and restarted `identity-event-source`; verified live via a
  streaming log monitor that injected-suspicious events now score
  `ALERT`/negative, matching the behavior already confirmed for
  `ics-event-source` (attack ticks scoring reconstruction error 9-136+
  against a 0.009223 threshold, normal ticks staying under 0.005).
- Initialized git, committed, and pushed `live-target-lab` to its own new
  repo: https://github.com/samuelgtetteh/live-target-lab (kept separate
  from `cloud-target-lab` — different purpose, confirmed with the user
  rather than merging them).
- Wrote [`docs/system_landscape.md`](system_landscape.md): a map of how the
  4 repos (this one, `cloud-target-lab`, `live-target-lab`, the exhibit
  docs) and their containers fit together, the runtime port/wiring diagram,
  why the event sources synthesize instead of replay, both generator bugs
  found and fixed (ICS noise scaling, identity auth-type vocabulary) so they
  aren't rediscovered from scratch later, and a "when something looks
  broken, check in this order" section.
- Found a stale duplicate backend container (`angry_clarke`, image
  `regmap-api`, port 8001) left running from an earlier manual test,
  separate from the one everything actually points at (`RedMap`, port
  2500). Documented it as a known quirk rather than deleting it outright.
- Worked through PowerShell-specific testing gotchas (bash-style `\` line
  continuation and `-H`/`-d` flags don't work the same way in PowerShell)
  and documented working `curl.exe` one-liners and native
  `Invoke-RestMethod` equivalents for hitting `/identity/score` and
  `/ics/score` manually.
- Built log tooling under `docs/logs/` (gitignored output, tracked scripts):
  - `snapshot_logs.ps1` — one-time dump of each container's full log
    history into a timestamped folder.
  - `start_live_logging.ps1` — continuously tails all 4 containers into
    separate per-container files in real time, for as long as it runs.

**Open items for next session:**
- `angry_clarke` (stale duplicate `regmap-api` container on port 8001) is
  still running — stop it if it's confirmed unused, to stop confusing
  `docker ps` output.
- `control-advisor/scanner/cloud_scan.py` (cloud/IaC scan against
  `cloud-target-lab`) is still standalone-only — not wired into
  `cli.py`'s interactive menu.
- The compound-negation misclassification in the Control Advisor interview
  LLM flow (e.g. "no, anyone can open them" read as "yes") is a known,
  unresolved limitation — revisit if it keeps recurring.
- Two leftover files from an earlier, since-abandoned approach are sitting
  untracked in the working tree and were deliberately left out of today's
  commit: `backend/ics_event_simulator.py` and
  `backend/identity_event_simulator.py` (one-shot CSV-replay simulators,
  superseded by `live-target-lab`'s synthesize-based generators). Also
  `nb03_temp.json` at the repo root looks like a stray scratch file from
  earlier notebook work. None of the three are referenced by anything
  currently in use — worth deleting once confirmed safe, rather than
  carrying them forward indefinitely.
