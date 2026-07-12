"""
Act layer (Track C, Phase C3): pluggable responders that fire when the Decide layer (C2)
raises an alert, with every response recorded in the durable `actions` audit table.

Responders (chosen by alert severity — see ROUTING):
  * log     — always. A structured, recorded acknowledgement that the alert was handled.
  * ticket  — medium/high. Creates a ticket STUB (recorded); a real deployment would call a
              tracker (Jira/ServiceNow) here.
  * webhook — high, and only if ACTION_WEBHOOK_URL is set. POSTs the alert JSON to that URL
              using stdlib urllib (no new dependency), best-effort.

Dispatch is inline: policy.evaluate() calls dispatch(alert) for each newly-created alert, so the
pipeline is Record -> Decide -> Act end to end. dispatch(alert) is the seam where a production
system would instead emit to a stream consumed by a separate responder service (Exhibit 14 sec 9).
Everything is best-effort: a responder that raises is recorded with status='failed' and never
propagates, so Act can never break scoring or evaluation.
"""
import json
import os
import urllib.request
from typing import Optional

from verdict_store import record_action

ACTION_WEBHOOK_URL = os.environ.get("ACTION_WEBHOOK_URL", "").strip()

# severity -> ordered list of responders to run
ROUTING = {
    "high": ["log", "ticket", "webhook"],
    "medium": ["log", "ticket"],
    "low": ["log"],
}


def _summary(alert: dict) -> str:
    d = alert.get("detail") or {}
    reason = d.get("reason") if isinstance(d, dict) else None
    return (f"[{alert.get('severity', '?').upper()}] {alert.get('rule')} "
            f"({alert.get('model')}/{alert.get('subject')}): "
            f"{reason or alert.get('verdict_count')} contributing verdict(s)")


def _log(alert: dict) -> tuple[str, Optional[dict]]:
    line = _summary(alert)
    print(f"[ACTION:log] alert {alert.get('id')} :: {line}", flush=True)
    return "ok", {"message": line}


def _ticket(alert: dict) -> tuple[str, Optional[dict]]:
    # Ticket stub — a real deployment would POST to a tracker and store the returned id.
    ticket_ref = f"SEC-{alert.get('id')}"
    return "ok", {"ticket_ref": ticket_ref, "title": _summary(alert), "system": "stub"}


def _webhook(alert: dict) -> tuple[str, Optional[dict]]:
    if not ACTION_WEBHOOK_URL:
        return "skipped", {"reason": "ACTION_WEBHOOK_URL not configured"}
    payload = json.dumps({"type": "security_alert", "alert": alert}).encode("utf-8")
    req = urllib.request.Request(ACTION_WEBHOOK_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:  # best-effort; caller wraps errors
        return "ok", {"url": ACTION_WEBHOOK_URL, "status": resp.status}


_RESPONDERS = {"log": _log, "ticket": _ticket, "webhook": _webhook}


def dispatch(alert: dict) -> list[int]:
    """Run the responders routed for this alert's severity; record each action; return the
    recorded action ids. Never raises."""
    if not alert:
        return []
    severity = alert.get("severity", "medium")
    action_ids: list[int] = []
    for name in ROUTING.get(severity, ["log"]):
        try:
            status, detail = _RESPONDERS[name](alert)
        except Exception as exc:  # a responder failure must not break the pipeline
            status, detail = "failed", {"error": str(exc)}
        try:
            action_ids.append(record_action(alert["id"], name, status, detail))
        except Exception:
            pass
    return action_ids
