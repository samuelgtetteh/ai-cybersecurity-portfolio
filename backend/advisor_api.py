"""
Compliance Advisor API — exposes the control-advisor toolkit (previously a PowerShell/CLI tool)
over HTTP so the whole "scan -> answer questions -> get documents" flow runs from the browser.

Pipeline (mirrors control-advisor/cli.py, minus the blocking input()/print()):
  detect environment -> scan (network or cloud) -> map discovered categories to NIST 800-53
  controls (RegMap embedder) -> an adaptive interview (rendered as a browser form) -> prioritize
  -> generate DOCX / XLSX / JSON reports for download.

Design notes:
  * The interview questions are static/adaptive data (interview.ENVIRONMENT_QUESTIONS +
    FOLLOWUP_QUESTIONS with deterministic triggers). We serve them as a form and evaluate the
    triggers server-side, so we skip the CLI's slow LLM free-text interpretation entirely.
  * The LLM narrative steps (executive summary, drafted policy language) are SLOW and need Qwen;
    they are OPTIONAL (with_language) and degrade to a templated summary when unavailable, so the
    core flow is fast and works even without the LLM in the image.
  * Authorization reuses securescan.authz (loopback/private by default; SCAN_ALLOW_ANY to opt in),
    unified with the SecureScan tool.
  * control-advisor imports its modules by bare name, so we add its `scanner/` dir to sys.path.
"""
import ipaddress
import os
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# --- make the control-advisor toolkit importable (it imports modules by bare name) ---
_REPO = Path(__file__).resolve().parent.parent
_CA_SCANNER = _REPO / "control-advisor" / "scanner"
if _CA_SCANNER.is_dir() and str(_CA_SCANNER) not in sys.path:
    sys.path.insert(0, str(_CA_SCANNER))

ADVISOR_AVAILABLE = True
ADVISOR_IMPORT_ERROR = None
try:
    import environment_detect
    import network_scan
    import cloud_scan
    import control_mapper
    import baseline_controls
    import interview as ca_interview
    import report_export
    import docx_report
    import xlsx_report
    import semantic_answer as ca_semantic  # embedder-based free-text interpretation
    try:
        import draft_language  # optional LLM step
    except Exception:
        draft_language = None
except Exception as e:  # toolkit not present (e.g. not copied into the image)
    ADVISOR_AVAILABLE = False
    ADVISOR_IMPORT_ERROR = str(e)

try:
    from securescan import authz as scan_authz
except Exception:
    scan_authz = None

router = APIRouter(prefix="/advisor", tags=["advisor"])

# Where generated reports are written + an in-process index (report_id -> file paths + meta).
REPORTS_DIR = Path(os.environ.get("ADVISOR_REPORTS_DIR", str(_REPO / "reports")))
_REPORTS: dict = {}


def _require_available():
    if not ADVISOR_AVAILABLE:
        raise HTTPException(status_code=503,
                            detail=f"compliance advisor unavailable: {ADVISOR_IMPORT_ERROR}")


def _normalize_target(raw: str) -> str:
    """Trim whitespace (incl. spaces around a '/') and canonicalize a CIDR to its network form,
    so '10.0.0.1 / 24' -> '10.0.0.0/24'. Leaves hostnames/single IPs as the whitespace-stripped
    string."""
    t = "".join((raw or "").split())
    try:
        return str(ipaddress.ip_network(t, strict=False))
    except ValueError:
        return t


def _authorize(target: str) -> None:
    """Authorize a scan target (single host or CIDR). Reuses the SecureScan allowlist policy."""
    allow_any = bool(scan_authz and scan_authz.allow_any())
    # CIDR / network target
    try:
        net = ipaddress.ip_network(target, strict=False)
        if allow_any or net.is_private or net.is_loopback or net.is_link_local:
            return
        raise HTTPException(status_code=403, detail=(
            f"{target} is a public range; scanning it is not authorized. Set SCAN_ALLOW_ANY=1 to "
            "authorize scanning any target (only where you are authorized to scan)."))
    except ValueError:
        pass
    # single host / hostname
    if scan_authz is None:
        return
    ok, reason = scan_authz.is_authorized(target)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)


# Scan providers offered in the UI. Physical is first and always available; cloud providers are
# listed so the user can choose their environment, with an honest 'implemented' flag (only AWS is
# wired today via boto3 — the others need their provider SDK/credentials).
PROVIDERS = [
    {"id": "physical", "label": "Physical / on-prem network", "kind": "network", "implemented": True,
     "note": "TCP discovery of a CIDR or single host on a network you are authorized to scan"},
    {"id": "aws", "label": "AWS (Amazon Web Services)", "kind": "cloud", "implemented": True,
     "note": "Control-plane audit via boto3; uses your AWS credentials"},
    {"id": "azure", "label": "Microsoft Azure", "kind": "cloud", "implemented": False,
     "note": "Planned — requires Azure credentials / SDK"},
    {"id": "gcp", "label": "Google Cloud (GCP)", "kind": "cloud", "implemented": False,
     "note": "Planned — requires GCP credentials / SDK"},
    {"id": "other", "label": "Other cloud / SaaS", "kind": "cloud", "implemented": False,
     "note": "Planned"},
]
_IMPLEMENTED_PROVIDERS = {p["id"] for p in PROVIDERS if p["implemented"]}

# Expanded, environment-determining interview questions (layered on top of control-advisor's base
# set). They classify WHAT KIND of environment we are looking at so a compliance template can be
# generated even without a scan. Same shape as the control-advisor questions.
EXTRA_QUESTIONS = [
    {"id": "deployment_model", "question": "Where does your infrastructure primarily run?",
     "descriptions": {"on_premises": "Your own data center / office servers",
                      "cloud": "Primarily public cloud", "hybrid": "A mix of on-prem and cloud",
                      "unsure": "Not sure"}},
    {"id": "cloud_providers", "question": "Which cloud providers do you use?", "multi": True,
     "descriptions": {"aws": "Amazon Web Services", "azure": "Microsoft Azure",
                      "gcp": "Google Cloud", "other": "Another provider", "none": "None"}},
    {"id": "has_ot_ics", "question": "Do you operate industrial / OT systems (SCADA, PLCs, building "
                                     "management, medical devices)?",
     "descriptions": {
         "yes": "Yes — we operate industrial or operational-technology systems such as SCADA, PLCs, "
                "building-management / HVAC controls, manufacturing equipment, or medical devices",
         "no": "No — we have no industrial, OT, or building-control systems; only regular IT",
         "unsure": "Not sure whether we have any OT/ICS systems"}},
    {"id": "remote_workforce", "question": "Do staff access systems remotely (VPN, remote desktop, "
                                           "or SaaS from anywhere)?",
     "descriptions": {
         "yes": "Yes — staff work remotely or access systems from outside the office via VPN, "
                "remote desktop, or cloud/SaaS apps",
         "no": "No — systems are only accessed on-site from the office network"}},
    {"id": "endpoints_managed", "question": "Are workstations and servers centrally managed "
                                            "(patching, configuration, antivirus)?",
     "descriptions": {
         "yes": "Yes — devices are centrally managed with automatic patching, standard "
                "configuration, and antivirus/EDR",
         "partial": "Partially — some devices are managed but others are not",
         "no": "No — devices are not centrally managed; users patch and configure their own",
         "unsure": "Not sure how devices are managed"}},
]


def _classify_environment(answers: dict) -> dict:
    """Derive a short 'what kind of environment' profile from the interview answers."""
    dep = answers.get("deployment_model") or ("hybrid" if answers.get("cloud_providers") else "unsure")
    clouds = [c for c in (answers.get("cloud_providers") or []) if c not in ("none",)]
    ot = answers.get("has_ot_ics") == "yes"
    exposed = answers.get("internet_facing") == "yes"
    bits = []
    bits.append({"on_premises": "on-premises", "cloud": "cloud-hosted", "hybrid": "hybrid cloud/on-prem"}
                .get(dep, "mixed"))
    if clouds:
        bits.append("cloud: " + ", ".join(clouds))
    if ot:
        bits.append("includes OT/ICS")
    if exposed:
        bits.append("internet-facing")
    sector = answers.get("sector")
    if sector and sector != "unsure":
        bits.append(f"sector: {sector}")
    return {"deployment_model": dep, "cloud_providers": clouds, "has_ot_ics": ot,
            "internet_facing": exposed, "summary": "; ".join(bits)}


@router.get("/providers")
def get_providers():
    """Scan providers the UI offers (physical first). `implemented` says which are wired today."""
    return {"providers": PROVIDERS}


# ------------------------------------------------------------------ environment
@router.get("/environment")
def get_environment():
    """Detect the runtime environment: local interfaces + suggested scan ranges, Docker, cloud
    instance/credentials. Powers the 'what can I scan?' prompt in the UI."""
    _require_available()
    try:
        env = environment_detect.detect_environment()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"environment detection failed: {e}")
    # Cap each interface's suggested scan range to a /24 — a raw netmask can be a /16 (65k hosts),
    # which is far too large to TCP-scan; a /24 is the sensible default to pre-fill.
    for itf in env.get("local_interfaces", []):
        ip = itf.get("ip")
        try:
            itf["suggested_range"] = str(ipaddress.ip_network(f"{ip}/24", strict=False))
        except (ValueError, TypeError):
            pass
    return env


# ------------------------------------------------------------------ scan + control mapping
class AdvisorScan(BaseModel):
    target: str = Field("", description="a CIDR (e.g. 192.168.1.0/24) or single host/IP (network mode)")
    provider: str = Field("physical", description="physical | aws | azure | gcp | other")
    cloud: bool = Field(False, description="(legacy) treat as provider=aws")
    region: str = Field("us-east-1", description="AWS region (cloud mode)")
    top_k: int = Field(3, ge=1, le=10, description="controls per discovered category")
    timeout: float = Field(0.5, gt=0, le=5)
    max_hosts: int = Field(256, ge=1, le=4096)


@router.post("/scan")
def advisor_scan(req: AdvisorScan):
    """Discover assets and map each discovered category to NIST 800-53 controls (via the RegMap
    embedder). Returns the raw scan report + the recommended controls per host."""
    _require_available()
    provider = "aws" if req.cloud else (req.provider or "physical").lower()
    if provider == "physical":
        if not req.target.strip():
            raise HTTPException(status_code=400, detail="a target CIDR or host is required for a network scan")
        target = _normalize_target(req.target)
        _authorize(target)
        try:
            scan_report = network_scan.scan(target, timeout=req.timeout, max_hosts=req.max_hosts)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"scan failed: {e}")
    elif provider == "aws":
        try:
            scan_report = cloud_scan.scan(region=req.region)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AWS scan failed (check credentials): {e}")
    elif provider in ("azure", "gcp", "other"):
        raise HTTPException(status_code=501, detail=(
            f"the '{provider}' provider is not wired yet — it needs that provider's credentials/SDK. "
            "Physical network and AWS are available today."))
    else:
        raise HTTPException(status_code=400, detail=f"unknown provider '{provider}'")
    try:
        recommendations = control_mapper.recommend_for_scan(scan_report, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"control mapping failed: {e}")
    return {"scan_report": scan_report, "recommendations": recommendations}


# ------------------------------------------------------------------ interview (adaptive form)
def _question_payload(q: dict) -> dict:
    """Shape an interview question for the UI: options come from its descriptions map."""
    descs = q.get("descriptions", {})
    return {"id": q["id"], "question": q["question"], "multi": bool(q.get("multi")),
            "options": [{"value": k, "description": v} for k, v in descs.items()]}


@router.get("/questions")
def base_questions(expanded: bool = Query(False, description="include the expanded "
                                          "environment-determining questions (for template mode)")):
    """The base environment questions (asked first), plus the business-name field and glossary.
    With expanded=true, also returns the extra questions that classify the environment type so a
    compliance template can be generated without a scan."""
    _require_available()
    questions = [_question_payload(q) for q in ca_interview.ENVIRONMENT_QUESTIONS]
    if expanded:
        questions += [_question_payload(q) for q in EXTRA_QUESTIONS]
    return {
        "business_name": {"id": "business_name", "question": "What is the organization / business name?",
                          "type": "text"},
        "questions": questions,
        "glossary": getattr(ca_interview, "GLOSSARY", {}),
    }


class FollowupReq(BaseModel):
    answers: dict = Field(default_factory=dict, description="answers so far (base questions)")
    categories: List[str] = Field(default_factory=list, description="categories from the scan")


@router.post("/followups")
def followup_questions(req: FollowupReq):
    """The conditional follow-up questions whose triggers fire given the answers + scan categories.
    Lets the browser render an adaptive interview without the LLM."""
    _require_available()
    cats = set(req.categories or [])
    out = []
    for q in getattr(ca_interview, "FOLLOWUP_QUESTIONS", []):
        trigger = q.get("trigger")
        try:
            fires = bool(trigger(cats, req.answers)) if trigger else True
        except Exception:
            fires = False
        if fires and q["id"] not in req.answers:
            out.append(_question_payload(q))
    return {"questions": out}


def _question_index(expanded: bool = True) -> dict:
    """id -> question dict, across base + (expanded) + follow-up questions, for interpretation."""
    qs = list(ca_interview.ENVIRONMENT_QUESTIONS)
    if expanded:
        qs += EXTRA_QUESTIONS
    qs += list(getattr(ca_interview, "FOLLOWUP_QUESTIONS", []))
    return {q["id"]: q for q in qs}


class InterpretReq(BaseModel):
    responses: dict = Field(default_factory=dict, description="{question_id: free-text answer}")


@router.post("/interpret")
def interpret_answers(req: InterpretReq):
    """Turn plain-English answers into structured option values using the RegMap embedder
    (semantic_answer) — so the interview is conversational, not tick-boxes. Returns, per question,
    the resolved value(s), a human label, and the match confidence for transparency. Needs no LLM;
    'business_name' passes through as free text."""
    _require_available()
    idx = _question_index(expanded=True)
    results = {}
    for qid, text in (req.responses or {}).items():
        text = (text or "").strip()
        if qid == "business_name":
            results[qid] = {"value": text, "label": text, "method": "text"}
            continue
        q = idx.get(qid)
        if not q:
            results[qid] = {"value": text, "label": text, "method": "unknown"}
            continue
        descs = q.get("descriptions", {})
        multi = bool(q.get("multi"))
        try:
            selected, details = ca_semantic.interpret(text, descs, multi=multi)
        except Exception as e:
            selected = ["unsure"] if multi else "unsure"
            details = {"method": "error", "error": str(e)}
        vals = selected if isinstance(selected, list) else [selected]
        results[qid] = {"value": selected, "label": ", ".join(str(v) for v in vals),
                        "method": details.get("method"), "score": details.get("score")}
    return {"results": results}


# ------------------------------------------------------------------ report generation
class ReportReq(BaseModel):
    scan_report: dict = Field(default_factory=dict, description="raw scan (empty for template-only mode)")
    recommendations: dict = Field(default_factory=lambda: {"hosts": []},
                                  description="mapped controls (empty for template-only mode)")
    answers: dict = Field(..., description="the interview answers (context)")
    with_language: bool = Field(False, description="LLM-drafted policy language + exec summary (slow; needs Qwen)")


def _categories_from(recommendations: dict) -> list:
    cats = set()
    for h in recommendations.get("hosts", []):
        cats.update(h.get("categories", []))
    return sorted(cats)


def _templated_summary(context: dict, final_report: dict, baseline: list) -> str:
    hosts = final_report.get("hosts", [])
    biz = context.get("business_name") or "the organization"
    return (f"Automated compliance assessment for {biz}. The scan reviewed {len(hosts)} host(s) and "
            f"mapped discovered services to NIST SP 800-53 controls, complemented by "
            f"{len(baseline)} baseline controls that a scan cannot detect. Controls are prioritized "
            f"(Critical/High/Medium/Low) by the organization's sector, regulated data, internet "
            f"exposure, and security maturity. Review the Critical and High items first.")


@router.post("/report")
def generate_report(req: ReportReq):
    """Prioritize the mapped controls against the interview answers, (optionally) draft policy
    language with the LLM, and write DOCX / XLSX / JSON reports. Returns the report id, the
    flattened rows for on-screen display, and download links."""
    _require_available()
    context = dict(req.answers or {})
    env_profile = _classify_environment(context)
    context.setdefault("environment_profile", env_profile["summary"])
    recommendations = dict(req.recommendations or {})
    recommendations.setdefault("cidr", None)          # template-only mode has no scan/cidr
    recommendations.setdefault("hosts", [])
    scan_report = req.scan_report or {"cidr": None, "results": []}
    try:
        final_report = ca_interview.prioritize_scan_recommendations(recommendations, context)
        baseline = ca_interview.prioritize_baseline_controls(
            baseline_controls.load_baseline_controls(), context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"prioritization failed: {e}")

    drafts = None
    summary = _templated_summary(context, final_report, baseline)
    llm_used = False
    if req.with_language and draft_language is not None:
        try:
            summary = draft_language.generate_executive_summary(final_report, baseline, context)
            drafts = draft_language.draft_language_for_report(final_report, baseline, context)
            llm_used = True
        except Exception:
            llm_used = False  # degrade silently to the templated summary; core report still ships

    try:
        rows = report_export.to_rows(final_report, baseline, drafts=drafts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"report flattening failed: {e}")

    report_id = uuid.uuid4().hex[:12]
    outdir = REPORTS_DIR / report_id
    outdir.mkdir(parents=True, exist_ok=True)
    biz = context.get("business_name") or "assessment"
    files = {}
    import json as _json
    try:
        json_path = outdir / "report.json"
        json_path.write_text(_json.dumps(
            {"context": context, "final_report": final_report, "baseline": baseline,
             "executive_summary": summary, "rows": rows}, default=str, indent=2), encoding="utf-8")
        files["json"] = "report.json"
        docx_path = outdir / "report.docx"
        docx_report.build_report(str(docx_path), final_report, baseline, context, summary,
                                 drafts=drafts, scan_report=scan_report)
        files["docx"] = "report.docx"
        xlsx_path = outdir / "report.xlsx"
        xlsx_report.build_report(str(xlsx_path), final_report, baseline, summary,
                                 drafts=drafts, business_name=biz)
        files["xlsx"] = "report.xlsx"
    except Exception as e:
        # a document builder failing shouldn't lose the whole report — return what we have
        raise HTTPException(status_code=500, detail=f"report generation failed: {e}")

    _REPORTS[report_id] = {"dir": str(outdir), "files": files, "business_name": biz,
                           "row_count": len(rows)}
    return {"report_id": report_id, "business_name": biz, "executive_summary": summary,
            "environment_profile": env_profile, "llm_used": llm_used, "rows": rows, "files": files,
            "download_base": f"/advisor/report/{report_id}/"}


_MEDIA = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "json": "application/json"}


@router.get("/report/{report_id}/{fmt}")
def download_report(report_id: str, fmt: str):
    """Download a generated report file (docx | xlsx | json)."""
    rec = _REPORTS.get(report_id)
    if not rec or fmt not in rec["files"]:
        raise HTTPException(status_code=404, detail="report or format not found")
    path = Path(rec["dir"]) / rec["files"][fmt]
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing")
    fname = f"{rec['business_name']}_compliance_report.{fmt}".replace(" ", "_")
    return FileResponse(str(path), media_type=_MEDIA.get(fmt, "application/octet-stream"),
                        filename=fname)


@router.get("/health")
def advisor_health():
    """Whether the advisor toolkit loaded, and whether the optional LLM language step is available."""
    return {"available": ADVISOR_AVAILABLE, "error": ADVISOR_IMPORT_ERROR,
            "llm_language": ADVISOR_AVAILABLE and draft_language is not None}
