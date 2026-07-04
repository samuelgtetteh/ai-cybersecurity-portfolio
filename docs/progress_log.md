# Progress Log

Dated entries of what changed each working session, so a new day can start by
reading the latest entry instead of reconstructing context from scratch.
Newest entry at the top.

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
