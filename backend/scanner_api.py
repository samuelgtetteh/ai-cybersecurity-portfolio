"""
SecureScan API (Phase 1): expose asset discovery + CVE mapping over HTTP, wired into the same app
as the detectors. Findings are recorded to the verdict store (model="scan") so they show up in the
live decisioning trail.

Endpoints (prefix /scan):
  POST /scan            — discover a host, map CVEs, return the report (and record it by default)
  GET  /scan/engines    — which scan engines are usable here + the authorization posture
  GET  /scan/authorize  — check whether a given target is authorized to scan (without scanning)

Safety: every scan passes through scanner.authz — loopback/private by default, anything else only
with an explicit opt-in (SCAN_ALLOW_ANY). An unauthorized target returns 403, not a scan.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from securescan import authz, discovery, engines

router = APIRouter(prefix="/scan", tags=["securescan"])


def _parse_ports(spec: Optional[str]) -> Optional[List[int]]:
    """Parse '22,80,443' or '1-1024' (or a mix) into a sorted unique port list. None -> engine default."""
    if not spec:
        return None
    out: set = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            lo, hi = token.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(token))
    return sorted(p for p in out if 0 < p <= 65535)


class ScanRequest(BaseModel):
    target: str = Field(..., description="host or IP to scan (must be authorized)")
    ports: Optional[str] = Field(None, description="e.g. '22,80,443' or '1-1024'; default = engine's common set")
    engine: str = Field("auto", description="auto | socket | nmap")
    with_cves: bool = Field(True, description="map discovered services to CVEs via NVD")
    max_per_service: int = Field(5, ge=1, le=20, description="max CVEs per service")
    record: bool = Field(True, description="record the scan to the verdict trail (model=scan)")
    timeout: float = Field(0.7, gt=0, le=10, description="per-port connect timeout (seconds)")
    delay: float = Field(0.0, ge=0, le=5, description="polite delay between ports (seconds)")


@router.post("")
def run_scan(req: ScanRequest):
    """Discover a single host, optionally map CVEs, and return the report. 403 if the target is
    not authorized; 400 on a bad engine / port spec."""
    try:
        ports = _parse_ports(req.ports)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid ports spec (use '22,80' or '1-1024')")
    target = "".join((req.target or "").split())  # tolerate stray whitespace in the target
    try:
        report = discovery.scan_and_report(
            target, ports=ports, engine=req.engine, with_cves=req.with_cves,
            max_per_service=req.max_per_service, timeout=req.timeout, delay=req.delay)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except engines.EngineUnavailable as e:
        raise HTTPException(status_code=400, detail=str(e))
    if req.record:
        report["verdict_id"] = discovery.record_report(report)
    return report


@router.get("/engines")
def scan_engines():
    """Engines usable in this environment + the current authorization posture."""
    return {"engines": engines.available(), "default": engines.get_engine("auto").NAME,
            "authorization": authz.describe()}


@router.get("/authorize")
def check_authorization(target: str = Query(..., description="host or IP")):
    """Whether `target` may be scanned here (does not scan)."""
    ok, reason = authz.is_authorized(target)
    return {"target": target, "authorized": ok, "reason": reason}
