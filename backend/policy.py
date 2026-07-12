"""
Decide layer (Track C, Phase C2): a policy/rules engine over the recorded verdict trail.

The Record layer (C1) captures every verdict; this layer reads a trailing window of that
trail and produces durable *alerts* — the derived decisions the Act layer (C3) will respond
to. Rules are deliberately simple and configurable (env-overridable), and crucially they can
weight decisions by each subject's HISTORICAL ground-truth outcomes (the feedback loop from
C1): a subject whose flagged verdicts have consistently turned out benign is a chronic false
positive and gets suppressed; one with confirmed-malicious history gets escalated. That is the
concrete payoff of persisting verdicts + feedback rather than reacting to raw scores.

Rules (all windowed on recorded_at):
  1. identity_burst  — >= IDENTITY_BURST_MIN flagged identity verdicts from one subject in the
     window (lateral-movement / credential-stuffing / access-breadth signal).
  2. ics_sustained   — >= ICS_SUSTAINED_MIN flagged ICS verdicts in the window (sustained event,
     mirroring the OT/ICS paper's min-run alarm filtering — not a single blip).
  3. high_severity   — a single verdict with an extreme score.

evaluate() is idempotent: an open alert for the same (rule, subject) within the window blocks a
duplicate, so it is safe to call on every /decision/alerts read or after every verdict.
"""
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import actions
from verdict_store import (get_alert, recent_alert_exists, record_alert, recent_verdicts,
                           subject_outcome_history)


def _int(env, default):
    try:
        return int(os.environ.get(env, default))
    except ValueError:
        return default


def _float(env, default):
    try:
        return float(os.environ.get(env, default))
    except ValueError:
        return default


WINDOW_SECONDS = _int("DECISION_WINDOW_SECONDS", 300)
IDENTITY_BURST_MIN = _int("IDENTITY_BURST_MIN", 3)     # flagged logins from one user -> burst
ICS_SUSTAINED_MIN = _int("ICS_SUSTAINED_MIN", 3)       # flagged ICS ticks -> sustained event
ICS_SEVERE_ERROR = _float("ICS_SEVERE_ERROR", 1.0)     # reconstruction error this high = severe
IDENTITY_SEVERE = _float("IDENTITY_SEVERE", -0.1)      # IsolationForest score this low = severe
SUPPRESS_MIN = _int("DECISION_SUPPRESS_MIN", 3)        # min labelled history to trust suppression


def _weight_severity(base: str, subject: Optional[str], model: str) -> Optional[str]:
    """Adjust a base severity by the subject's historical outcomes. Returns None to SUPPRESS
    (chronic false positive), or an escalated/de-escalated severity string."""
    h = subject_outcome_history(subject, model)
    mal, ben = h["malicious"], h["benign"]
    total = mal + ben
    if total >= SUPPRESS_MIN and mal == 0 and ben > 0:
        return None                       # consistently benign in the past -> suppress
    if mal > ben and mal > 0:
        return "high"                     # confirmed-bad history -> escalate
    if total >= SUPPRESS_MIN and ben > mal:
        return "low"                      # mostly benign -> de-escalate
    return base


def evaluate(now: Optional[datetime] = None) -> list[int]:
    """Scan the trailing window, apply the rules, dedup against open alerts, and persist any
    new alerts. Returns the ids of alerts created on this call."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(seconds=WINDOW_SECONDS)).isoformat()
    flagged = recent_verdicts(since, flagged_only=True)
    created: list[int] = []

    # rule 1: identity_burst — group flagged identity verdicts by subject
    by_subject: dict = defaultdict(list)
    for v in flagged:
        if v["model"] == "identity" and v["subject"]:
            by_subject[v["subject"]].append(v)
    for subject, vs in by_subject.items():
        if len(vs) < IDENTITY_BURST_MIN:
            continue
        if recent_alert_exists("identity_burst", subject, since):
            continue
        severity = _weight_severity("high", subject, "identity")
        if severity is None:
            continue  # suppressed as a chronic false positive
        created.append(record_alert(
            "identity_burst", "identity", subject, severity, WINDOW_SECONDS,
            [v["id"] for v in vs],
            detail={"reason": f"{len(vs)} flagged logins from {subject} within {WINDOW_SECONDS}s",
                    "history": subject_outcome_history(subject, "identity")}))

    # rule 2: ics_sustained — ICS has no per-account subject; count flagged ICS in the window
    ics = [v for v in flagged if v["model"] == "ics"]
    if len(ics) >= ICS_SUSTAINED_MIN and not recent_alert_exists("ics_sustained", None, since):
        created.append(record_alert(
            "ics_sustained", "ics", None, "high", WINDOW_SECONDS,
            [v["id"] for v in ics],
            detail={"reason": f"{len(ics)} sustained ICS anomalies within {WINDOW_SECONDS}s"}))

    # rule 3: high_severity — a single verdict with an extreme score, alerted immediately
    # (don't wait for N). Dedup key: identity by subject; ICS by a constant so a stream of
    # severe readings raises one open alert per window rather than storming.
    for v in flagged:
        score = v["score"]
        if score is None:
            continue
        if v["model"] == "ics" and score >= ICS_SEVERE_ERROR:
            key = "ics"
        elif v["model"] == "identity" and v["subject"] and score <= IDENTITY_SEVERE:
            key = v["subject"]
        else:
            continue
        if recent_alert_exists("high_severity", key, since):
            continue
        created.append(record_alert(
            "high_severity", v["model"], key, "high", WINDOW_SECONDS, [v["id"]],
            detail={"score": score, "reason": "single verdict with an extreme anomaly score"}))

    # Act layer (C3): fire responders for each newly-created alert (inline, best-effort).
    for alert_id in created:
        try:
            actions.dispatch(get_alert(alert_id))
        except Exception:
            pass

    return created
