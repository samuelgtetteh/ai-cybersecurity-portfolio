# Progress Log

Dated entries of what changed each working session, so a new day can start by
reading the latest entry instead of reconstructing context from scratch.
Newest entry at the top.

## 2026-07-11

**Identity paper: full scholarly expansion + two reproducibility fixes that changed the
headline. Robust-signal reframing (title changed).**

Expansion (local `paper/identity/`, gitignored; this log is the committed record):
- `paper.tex` rewritten from the ~600-word draft to a full ~4,600-word manuscript: Background,
  Threat Model, expanded 4-part Related Work (positioning vs Euler, LMDetect, Bowman's UA rule),
  Dataset (day-2 window + subsampling treatment), Method, and a Results section with per-feature
  attribution, feature-group ablation, leave-one-out, distributions, access-breadth rule, ranking
  (recall@FPR / precision@K), subsample invariance, and a prior-work positioning subsection; plus
  Discussion, Limitations, Conclusion.
- Added `euler` (King & Huang, TOPS 2023) and `lmdetect` (Zhou et al., arXiv 2411.10279) to
  `references.bib`; woven throughout.

New experiments (`paper/identity/eval_extras.py`; results appended to `results_identity.json`;
mirrored in self-contained tracked notebook `notebooks/07b_identity_extended_evaluation.ipynb`):
- Per-feature univariate AUC, feature-group Isolation Forests, leave-one-out, red-vs-normal
  distributions, access-breadth threshold rule, recall@FPR / precision@K, subsample invariance.

**Two determinism bugs found and fixed (this is why the headline moved):**
1. **Nondeterministic categorical encoding.** `sample[col].unique()` order is not stable in polars;
   since Isolation Forest treats the integer codes as ordinal, the ensemble AUC varied run-to-run
   (0.85-0.90). Fixed by sorting categories before encoding.
2. **Nondeterministic row order.** Streaming joins don't preserve order and IF samples rows by index,
   so the ensemble AUC still drifted. Fixed by a total-order row sort on all raw columns.
   After both fixes, base `auc` == extras `all_9.auc` == **0.900** exactly; fully reproducible.
   (The count features unique_pcs/hourly_count were always deterministic, so the central finding
   never depended on the bug.)

**Headline change (thesis reframed, user-approved "robust-signal framing"):**
- The old draft claimed access breadth (0.905) *beats* the ensemble (0.853). The 0.853 was an
  artifact of the buggy encoding. Corrected deterministic numbers: **ensemble AUC 0.900**
  (CI 0.893-0.908); **access breadth alone 0.905** (matches ensemble); **auth_type 0.931**
  (nominally highest but a fragile ordinal encoding of an unordered categorical -- documented as
  the fragility we hit); **login volume 0.423** (below chance -- noisiest accounts are legitimate
  service accounts, max 65,781 logins / 4,358 machines).
- **New operational finding that carries the paper:** at 10% FPR, access breadth recovers **0.96**
  of red-team logins vs the ensemble's **0.65** -- access breadth *dominates* in the low-FPR triage
  regime even though AUCs tie. Near-parameter-free rule (unique_pcs >= 20 machines) catches 47/48 at
  10% FPR.
- Title changed: "Access Breadth over Ensembles" -> **"Access Breadth as a Robust Signal for
  Credential-Based Lateral Movement: A Red-Team Feature-Attribution Study on the LANL Dataset."**
  Affiliation + artifact footnote (notebooks 07 + 07b) added.
- Verification: 44-point automated check passes; base==extras consistency confirmed; all citations
  resolve; figures present; stale 0.853 / "beats the ensemble" claims removed.

## 2026-07-10

**OT/ICS paper: full manuscript expansion + peer-review revision with new
experiments. Two major findings.**

Paper expansion (local `paper/ot_ics/`, gitignored — this log is the committed
record):
- `paper.tex` hand-expanded from the ~1,500-word generated draft to a full
  ~7,500-word manuscript (Background, Threat Model, dedicated pitfall sections,
  Experimental Setup, expanded Results, Limitations). **`paper.tex` is now
  hand-authored — do NOT re-run `build_latex.py` for ot_ics or it will clobber
  it.** The `.docx` variants still contain the old short text (out of sync).
- Added `kus22` (CPSS '22 "False Sense of Security"), `aslam24` (ImpAE, SSCE
  2024), `abshari26` (CPS anomaly-detection survey) to `references.bib`; all
  cited in the body. Target venue recommendation on record: USENIX CSET first
  (evaluation/reproducibility genre; HAI's home venue), IEEE Access fallback.
- Two peer reviews performed (mine: evidentiary gaps; external AI review:
  narrative framing — partially unreliable, two comments already satisfied in
  text, one fabricated quote). Merged into an 11-item revision plan, executed.

New experiments (`paper/ot_ics/eval_extras.py`, `leakage_attribution.py`;
results appended to `results_ot_ics.json`; runbook updated in `paper/README.md`):
- **Finding 1 — leaked model quantified exactly.** The original leaked artifact
  was preserved (`autoencoder_hai_leaky_backup.pth`, 63 inputs = 59 sensors +
  `attack`,`attack_P1/P2/P3`): ROC AUC = 1.000000, AP = 1.000000 exactly;
  100% recall @ 1% FPR (clean model: 64.2%). Label channels: MSE 50.1 on
  attacks vs 1.4e-4 on normals (5 orders of magnitude). **Deeper result: the
  contamination is model-deep** — sensor-channel errors ALONE still give AUC
  1.0 (leaked inputs steer the latent code), so a leaked model cannot be
  salvaged at scoring time; only retraining fixes it. New figure
  `figures/leakage_channels.png`.
- **Finding 2 — second pitfall: cross-session normal contamination.** Notebook
  04 pooled ALL FOUR files' normal rows before the 80/20 split, so ~80% of
  test-file normals (and the scaler) were seen in training by the deployed
  model. A strict session-disjoint retrain (identical arch/hypers: 50 epochs,
  batch 256, Adam lr=1e-3, seed 42; trained on 495,021 train-file normals;
  new artifacts `autoencoder_hai_strict.pth`/`scaler_hai_strict.pkl`) scores
  **AUC 0.869 / AP 0.682** vs the pooled 0.929/0.733. The paper now reports
  the full honesty ladder: leaked 1.000 -> pooled 0.929 -> strict 0.869.
- Nominal-vs-realized FPR calibration: percentile thresholds calibrated on
  held-out same-session normals overshoot on test-session normals by 2.1x
  (90th pct) to 26.2x (99.9th); default threshold: 9.1% same-session -> 20.1%
  test-session. The STRICT model is worse: nominal 5% -> realized 75.4% (15x),
  nominal 1% -> 53.4% (53x). Honest training improves ranking, worsens
  fixed-threshold calibration.
- Temporal alarm aggregation (min-run-length k): at p99 threshold, k=10 cuts
  alert episodes 1,788 -> 179 (10x) with segment recall 89.5% -> 84.2%; at the
  default threshold 7,946 -> 247 (32x), still catching 36/38 attack segments.
  38 labelled attack segments total in test1+test2.
- Per-process AUC per method: AE 0.932/0.979/0.897 (P1/P2/P3) vs PCA
  0.881/0.903/0.725 vs IF 0.806/0.837/0.719 — baselines fail hardest on P3.
- Block bootstrap (1-h blocks, 500 resamples): AUC 0.929 CI95 [0.893, 0.960];
  AP 0.733 CI95 [0.613, 0.827].
- Label structure: 5,169 test rows carry multiple per-process labels
  (why P1+P2+P3 counts = 22,696 > 17,527 global attacks); 0 unattributed;
  no attack_P4 column exists in HAI 21.03.
- Paper also gained: affiliation, artifact-URL footnote (GitHub + notebook 05),
  SWaT/WADI leakage warning, threshold-provenance paragraph (default 0.009223
  = 95th pct of pooled-split validation normals ~= 90.8th pct of train-session
  normals), threat-model->triage bridge, eTaPR reframed as thesis validation.
- Verification: 72-point automated check — every paper number matches
  `results_ot_ics.json`; all citations resolve; all 5 figures exist; no
  dangling refs.

**Consistency updates applied (dual-protocol presentation, user-approved):**
- `README.md`: Results-at-a-Glance row now "0.929 (pooled) / 0.869
  (session-disjoint)"; OT/ICS section rewritten around the honesty ladder
  (leaked 1.000000 exact -> pooled 0.929 w/ CI -> strict 0.869), calibration
  inflation note, alarm-aggregation row; repo layout lists notebook 05b.
- `Exhibit 13` DOCX: inserted new §4.4 "Protocol Audit: Leakage Quantified
  Exactly and a Session-Disjoint Re-Evaluation (July 2026)" (patched in place
  via python-docx; two paragraphs covering both findings, ladder, calibration,
  alarm filtering — framed as evidence of scientific rigor for NIW).
- `notebooks/05b_ot_ics_extended_evaluation.ipynb` (tracked, self-contained):
  mirrors eval_extras.py + leakage_attribution.py — leaked-model exact eval +
  channel attribution figure, strict retrain (loads deterministic artifact if
  present), nominal-vs-realized FPR, temporal aggregation, per-process AUC,
  block bootstrap. Executed with outputs embedded. Paper artifact footnote
  updated to cite notebooks 05 + 05b.

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

Papers finalized (local `paper/`; see `paper/README.md` for the full runbook):
- **eTaPR** computed for OT/ICS via `faster-eTaPR` (compute_etapr.py, with a documented
  sklearn compat shim): eTaPR-F1 ~0.32 (test1) / 0.61 (test2) at the 99th-pct
  threshold — below the HAICon leaderboard (0.84–0.94 on HAI 21.03), as expected
  for a plain autoencoder; added to the paper with honest caveats.
- **references.bib** synced to the full verified reference lists for all three papers
  (generator: scratchpad/generate_bib.py; 29 / 25 / 25 entries).
- **LaTeX / arXiv**: `paper.tex` generated per paper (arXiv-ready `article` class,
  native math, booktabs tables, figures, `\citep` against references.bib; generator
  scratchpad/build_latex.py). Verified 0 double-escape artifacts and every `\citep`
  key resolves in the bib. Compile on Overleaf/arXiv (no local TeX toolchain here).
- **Venue variants**: `paper_{cs,cset,ieee,mdpi}.docx` for each paper via the
  build_paper.py venue flag (title-page label; swap the LaTeX documentclass for a
  venue's real template).

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
