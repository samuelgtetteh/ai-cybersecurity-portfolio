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


# ------------------------------------------------------------------ environment
@router.get("/environment")
def get_environment():
    """Detect the runtime environment: local interfaces + suggested scan ranges, Docker, cloud
    instance/credentials. Powers the 'what can I scan?' prompt in the UI."""
    _require_available()
    try:
        return environment_detect.detect_environment()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"environment detection failed: {e}")


# ------------------------------------------------------------------ scan + control mapping
class AdvisorScan(BaseModel):
    target: str = Field(..., description="a CIDR (e.g. 192.168.1.0/24) or single host/IP")
    cloud: bool = Field(False, description="audit AWS via boto3 instead of a network scan")
    region: str = Field("us-east-1", description="AWS region (cloud mode)")
    top_k: int = Field(3, ge=1, le=10, description="controls per discovered category")
    timeout: float = Field(0.5, gt=0, le=5)
    max_hosts: int = Field(256, ge=1, le=1024)


@router.post("/scan")
def advisor_scan(req: AdvisorScan):
    """Discover assets and map each discovered category to NIST 800-53 controls (via the RegMap
    embedder). Returns the raw scan report + the recommended controls per host."""
    _require_available()
    if req.cloud:
        try:
            scan_report = cloud_scan.scan(region=req.region)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"cloud scan failed (credentials?): {e}")
    else:
        _authorize(req.target)
        try:
            scan_report = network_scan.scan(req.target, timeout=req.timeout, max_hosts=req.max_hosts)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"scan failed: {e}")
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
def base_questions():
    """The base environment questions (asked first), plus the business-name field and glossary."""
    _require_available()
    return {
        "business_name": {"id": "business_name", "question": "What is the organization / business name?",
                          "type": "text"},
        "questions": [_question_payload(q) for q in ca_interview.ENVIRONMENT_QUESTIONS],
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


# ------------------------------------------------------------------ report generation
class ReportReq(BaseModel):
    scan_report: dict
    recommendations: dict
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
    try:
        final_report = ca_interview.prioritize_scan_recommendations(req.recommendations, context)
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
                                 drafts=drafts, scan_report=req.scan_report)
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
            "llm_used": llm_used, "rows": rows, "files": files,
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
