"""
Decision-layer API (Track C).

Phase C1 exposes the recorded verdict trail; the logging/feedback extension adds a
complete request audit, a ground-truth feedback channel, and live detection metrics.
Later phases (Decide/Act) add /decision/alerts and action endpoints on this router.

Endpoints read/write the durable trail in verdict_store — the authoritative real-time
record the stateless scorer lacked (Exhibit 14 section 3). Ground truth is decoupled
from scoring: any live client (analyst UI, SOAR, ticket-resolution webhook, or a test
event source) attaches the true label to a specific decision via /verdicts/{id}/feedback,
using the X-Verdict-Id the backend returns on every scored response.
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import ai_triage
import policy
from verdict_store import (close_alert, enforce_retention, get_alert, max_verdict_id, metrics,
                           query_actions, query_alerts, query_requests, query_verdicts,
                           set_disposition, set_ground_truth, stats, verdicts_since)

router = APIRouter(prefix="/decision", tags=["decision"])


def _overview() -> dict:
    """One aggregated snapshot for the live dashboard: system stats, per-model metrics, the open
    alert queue (priority-sorted), the most recent verdicts, and recent responder actions."""
    return {
        "stats": stats(),
        "metrics": {"all": metrics(), "identity": metrics("identity"), "ics": metrics("ics")},
        "alerts": query_alerts(status="open", limit=25),
        "recent_verdicts": query_verdicts(limit=25),
        "actions": query_actions(limit=15),
    }


@router.get("/verdicts")
def get_verdicts(
    model: Optional[str] = Query(None, description="identity | ics | regmap"),
    subject: Optional[str] = Query(None, description="e.g. a source user"),
    flagged: Optional[bool] = Query(None, description="filter to anomalies only"),
    labeled: Optional[bool] = Query(None, description="filter to verdicts with ground truth"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Most-recent-first slice of the recorded verdict trail (incl. request metadata
    and any attached ground truth)."""
    return query_verdicts(model=model, subject=subject, flagged=flagged,
                          labeled=labeled, limit=limit)


@router.get("/requests")
def get_requests(limit: int = Query(100, ge=1, le=1000)):
    """Audit of non-scored requests (health checks, errors, validation failures)."""
    return query_requests(limit=limit)


@router.get("/stats")
def get_stats():
    """Coverage totals: verdicts, flagged, labelled, audited requests, per model, + retention caps."""
    return stats()


@router.post("/retention/enforce")
def retention_enforce():
    """Immediately trim the log tables to their FIFO caps (oldest evicted). Trimming also happens
    automatically on insert (batched) and at startup; this is a manual/on-demand trigger."""
    return enforce_retention()


@router.get("/metrics")
def get_metrics(model: Optional[str] = Query(None, description="identity | ics | regmap")):
    """Live confusion matrix + precision/recall/specificity over labelled verdicts."""
    return metrics(model=model)


class Feedback(BaseModel):
    ground_truth: str  # 'malicious' | 'benign' (synonyms accepted)


@router.post("/verdicts/{verdict_id}/feedback")
def submit_feedback(verdict_id: int, feedback: Feedback):
    """Attach the true label to a recorded verdict — the feedback loop that lets the
    decision layer measure and improve its decisions. verdict_id is the value returned
    in the X-Verdict-Id response header of the original scored request."""
    try:
        updated = set_ground_truth(verdict_id, feedback.ground_truth)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail=f"no verdict with id {verdict_id}")
    return {"verdict_id": verdict_id, "ground_truth": feedback.ground_truth, "recorded": True}


@router.get("/alerts")
def get_alerts(
    status: Optional[str] = Query("open", description="open | closed (null for all)"),
    model: Optional[str] = Query(None, description="identity | ics | regmap"),
    auto_evaluate: bool = Query(True, description="run the policy rules before returning"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Derived decisions (Decide layer). By default runs the policy rules over the current
    window first, so the result reflects the live trail. Pass status= (omit for all)."""
    if auto_evaluate:
        policy.evaluate()
    return query_alerts(status=None if status in (None, "", "all") else status,
                        model=model, limit=limit)


@router.post("/evaluate")
def run_evaluate():
    """Explicitly run the policy rules over the current window; returns any new alert ids."""
    created = policy.evaluate()
    return {"created_alert_ids": created, "count": len(created)}


@router.get("/actions")
def get_actions(
    alert_id: Optional[int] = Query(None, description="filter to one alert's actions"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Audit of responses the Act layer took (log / ticket / webhook) per alert."""
    return query_actions(alert_id=alert_id, limit=limit)


@router.post("/alerts/{alert_id}/close")
def close(alert_id: int):
    """Analyst resolution: mark an alert closed (removes it from the open queue)."""
    if not close_alert(alert_id):
        raise HTTPException(status_code=404, detail=f"no alert with id {alert_id}")
    return {"alert_id": alert_id, "status": "closed"}


@router.post("/alerts/{alert_id}/reassess")
def reassess_alert(alert_id: int):
    """LLM-assisted (advisory) re-prioritization of one alert. Stores {priority, disposition,
    rationale}; priority is clamped to the severity floor. Kept out of the scoring/evaluate hot
    path — invoke explicitly (analyst action or a scheduled sweep)."""
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"no alert with id {alert_id}")
    a = ai_triage.assess(alert)
    set_disposition(alert_id, a["priority"], a["disposition"], a["rationale"])
    return {"alert_id": alert_id, **a}


@router.post("/reassess")
def reassess_open(limit: int = Query(50, ge=1, le=500)):
    """Reassess the open-alert queue in bulk (advisory). Returns the new priority/disposition per
    alert. Note: with an in-process LLM this is slow for many alerts; a sidecar LLM makes it cheap."""
    updated = []
    for alert in query_alerts(status="open", limit=limit):
        a = ai_triage.assess(alert)
        set_disposition(alert["id"], a["priority"], a["disposition"], a["rationale"])
        updated.append({"alert_id": alert["id"], "priority": a["priority"],
                        "disposition": a["disposition"], "llm_used": a["llm_used"]})
    return {"reassessed": len(updated), "alerts": updated}


@router.get("/alerts/{alert_id}/triage")
def alert_triage(alert_id: int):
    """AI triage (Track E): a concise analyst summary + the most relevant compliance controls
    for this alert (RAG over the corpus; LLM-written when the local model is available, else a
    templated summary). Heavy models load lazily on first call."""
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"no alert with id {alert_id}")
    return {"alert_id": alert_id, **ai_triage.triage(alert)}


@router.get("/overview")
def get_overview():
    """Aggregated snapshot powering the dashboard (single call; also the SSE payload shape)."""
    return _overview()


@router.get("/stream")
async def stream():
    """Server-Sent Events feed for the live dashboard. Pushes an initial overview, then every
    ~1.5s pushes any new verdicts plus a refreshed overview — one persistent connection, no
    client polling."""
    async def gen():
        last = max_verdict_id()
        yield f"data: {json.dumps({'type': 'init', 'overview': _overview()})}\n\n"
        while True:
            await asyncio.sleep(1.5)
            new = verdicts_since(last, limit=200)
            if new:
                last = new[-1]["id"]
            yield f"data: {json.dumps({'type': 'tick', 'new_verdicts': new, 'overview': _overview()})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/health")
def health():
    return {"status": "ok"}
