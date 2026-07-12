# Bookmark: SecureScan + Integrated-Platform Roadmap

**Status: BOOKMARKED 2026-07-12 — reviewed, not started. Do not begin until the user says so.**
This captures the shared "SecureScan" tool vision and the "integrated platform / real-world
applications" narrative, mapped against what already exists in this repo, so we can work through
it phase by phase later (same cadence as the three papers: a working artifact per phase).

---

## TL;DR — what we already have vs. what's genuinely new

The shared plan predates most of the current platform, so several pieces it proposes as new are
already built, and its file/exhibit numbers are stale (see "Numbering" below).

### Already built (reuse, don't rebuild)
| Vision element | Status | Where |
|---|---|---|
| RegMap — NIST 800-53 ↔ HIPAA NLP mapping (Component 1) | **BUILT** | `/map`, fine-tuned `models/regmap-embedder`, RegMap paper, Exhibit 11 |
| Identity anomaly detection (Component 2) | **BUILT** | `/identity/score`, Identity paper, Exhibit 12 |
| OT/ICS intrusion detection (Component 3) | **BUILT** | `/ics/score`, OT/ICS paper, Exhibit 13 |
| Real-time decisioning (Record→Decide→Act→AI triage) | **BUILT** | `backend/` decision layer, Exhibit 16 |
| **Unified/consolidated SOC view across the 3 detectors** | **BUILT** | live SSE dashboard shows Identity/OT-ICS/Compliance together, one priority alert queue, actions — this is much of the "integrated platform / unified alert" idea already realized for the existing components |
| Analyst case management + feedback loop + allowlist | **BUILT** | Exhibit 17, alert case drawer |
| Live continuous monitoring + FIFO log + webhook action | **BUILT** | dashboard + `actions.py` (a webhook responder already exists) |
| Browser-configurable limits/thresholds | **BUILT (BC.1)** | `settings.py`, settings drawer |

### Genuinely new (this is the SecureScan build)
| SecureScan phase | Status | Notes / leverage |
|---|---|---|
| P1 Asset discovery + CVE mapping (nmap → NVD) | **NOT BUILT** | net-new; nmap + NVD API |
| P2 Hardening assessment (config/baseline checks) | **NOT BUILT** | net-new; per-OS check modules |
| P3 CVE → NIST 800-53 control recommendation | **NOT BUILT** | **highest-value; reuses RegMap.** MVP = CVE→CWE (NVD gives CWE) → CWE/keyword → 800-53 crosswalk; upgrade = the RegMap embedder run "in reverse" (CVE text ↔ control text) |
| P4 `/scan` API + Docker (add nmap) | **NOT BUILT** | net-new endpoint, BUT the FastAPI/Docker/Record→Decide→Act pattern is established — SecureScan findings can flow into the SAME verdict store/alert queue as a new "model" (e.g. `model="scan"`) and appear on the existing dashboard |
| P5 Scheduled re-scan + drift alerting | **NOT BUILT** | alerting/webhook infra exists; scheduler (APScheduler) + drift detection are new |
| Integration NIW exhibit (healthcare scenario + diagram + gov-priority table) | **NOT WRITTEN** | references Exhibits 11–17; the "unified alert" it describes is partly demonstrable today with the 3 existing detectors |

---

## SecureScan — phase plan (to build later)

**Tool goal:** given a target host/range → discover hosts, ports, services/OS → map to CVEs →
check basic hardening → recommend the exact NIST 800-53 controls → expose via API/UI.

- **P1 — Discovery & CVE mapping (MVP).** `scanner/discovery.py`: `scan_host(ip)` via
  `python-nmap` (-sV) → open ports + service + version + CPE; `fetch_cves(cpe)` via the NVD 2.0
  API (rate-limited; use an NVD API key). Output structured JSON + a notebook artifact. ~4–6h.
- **P2 — Hardening assessment.** `scanner/hardening/` rule modules (e.g. SMB signing/SMBv1, RDP
  NLA, TLS version, SSH password-auth, default creds). Annotate each CVE hardened/unhardened;
  per-host hardening score. ~6–8h.
- **P3 — Control recommendation.** CVE→NIST 800-53. Start rule-based (CVE→CWE→control crosswalk);
  upgrade to NLP using the existing RegMap embedder (semantic CVE↔control match). Endpoint returns
  controls + implementation guidance ("Remediation Roadmap" per host). ~4h rule-based.
- **P4 — Integration & API.** `backend/scanner_api.py` (`POST /scan`); Docker image gets `nmap`;
  **feed findings into the existing verdict store/decision layer** so scans show up in the live
  dashboard and alert queue like the other detectors. ~3h.
- **P5 — (optional) Continuous monitoring.** APScheduler re-scan on a schedule; alert on new CVEs
  / hardening drift via the existing webhook action; posture-over-time view. Great for the demo
  video; not required for NIW.

### Precedence
P1 → P2 → P3 → P4 (each builds on the prior). P3 can start in parallel with P2 (it only needs the
CVE list from P1). P5 last. Integration exhibit can be drafted once P4 makes the demo end-to-end.

---

## Integrated-platform narrative (NIW)
The healthcare "attack lifecycle" scenario (discover → CVE → hardening → recommend controls →
identity anomaly → OT anomaly → unified SOC alert) is the NIW framing that ties all components
into "predicted → detected → recommended → audit evidence."
- **Deliverable:** a new integration exhibit — concrete healthcare scenario, a block diagram of
  component interaction, and a table mapping each component to U.S. gov priorities (CISA CPGs,
  NIST CSF, DHS critical-infrastructure sectors). References Exhibits 11–17.
- Much of the "unified alert" is already demonstrable with the 3 existing detectors on the live
  dashboard; SecureScan completes the "discovery + remediation" half of the lifecycle.

---

## Caveats / decisions to make before building
- **Authorization & scope:** nmap scanning is only appropriate against hosts you own or are
  explicitly authorized to test. Scope SecureScan to localhost / lab VMs / owned ranges by default
  and document that clearly (aligns with authorized-security-testing posture). No scanning of
  third parties.
- **NVD API key:** the public NVD API is heavily rate-limited; request a free API key and handle
  backoff. Consider caching CVE lookups.
- **Numbering (the shared plan is stale):** it says "notebook 05" and "Exhibit 14" — both are
  already used (05/06/07 are the paper evaluation notebooks; Exhibits 11–17 exist). Assign fresh
  numbers when we start, e.g. `notebooks/10_asset_cve_scan.ipynb`, Exhibit 18 (SecureScan) +
  Exhibit 19 (integrated platform).
- **New service vs. bolt-on:** recommend a separate `scanner/` package + `scanner_api.py` router
  mounted on the same app, writing verdicts as `model="scan"` so it reuses the whole
  Record→Decide→Act→dashboard stack rather than a parallel silo.

## Related
- `docs/browser_control_plan.md` (BC.1 done; BC.2/BC.3 pending) — the browser control plane.
- `docs/development_roadmap.md` — the broader post-submission roadmap.
- `docs/decision_layer_plan.md` — the platform SecureScan should plug into.
