"""
Verdict store — the durable "Record" layer of the decision pipeline (Track C).

Every model verdict produced by the RedMap backend (/identity/score, /ics/score, /map)
is persisted to an append-only SQLite trail, independent of any client, so the decision
layer has an authoritative record of what the system observed and decided. This is the
foundation of the Record -> Decide -> Act architecture (Exhibit 14 section 9): the backend
was previously a stateless scorer (Exhibit 14 section 3) that kept no such record.

Two tables:
  * verdicts  — one row per scored event: the model decision (flagged/score/subject/detail),
    request metadata (latency/status/client/path, filled by the app middleware), and an
    optional ground_truth label attached later via feedback.
  * requests  — one row per non-scored HTTP request (health checks, errors, validation
    failures) so the trail is complete: "whatever the live system looked at" is logged,
    whether or not it produced a decision.

Ground truth is deliberately DECOUPLED from scoring. In a live deployment nothing knows
the true label at scoring time; it arrives afterwards from an analyst, a downstream SOAR
system, a ticket resolution, or (in the test harness) the event source that injected the
event. Any such client attaches it via set_ground_truth(verdict_id, ...), keyed by the
X-Verdict-Id the backend returns on every scored response. metrics() then computes live
precision/recall/specificity from the labelled subset (the same confusion matrix the
Exhibit 14 tally produced from text logs, now straight from the DB).

Design notes: stdlib sqlite3 only (no new dependency); path from $VERDICT_DB, default
<repo>/data/verdicts.db; single process, so one module-level connection under a Lock is
correct. record_verdict_safe never raises — the Record layer must never break scoring.
A production deployment would swap the connection for Postgres/Redis and a decoupled
stream consumer at these same function boundaries.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("VERDICT_DB", BASE_DIR / "data" / "verdicts.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = Lock()
_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)

_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS verdicts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at  TEXT    NOT NULL,   -- ISO-8601 UTC, when the backend recorded it
        event_time   TEXT,               -- the event's own timestamp if supplied
        model        TEXT    NOT NULL,   -- 'identity' | 'ics' | 'regmap'
        subject      TEXT,               -- stable key for windowed rules (e.g. src_user)
        flagged      INTEGER NOT NULL,   -- 1 = anomaly / low-confidence, 0 = normal
        score        REAL,               -- model score (meaning is per-model)
        detail       TEXT,               -- JSON: model-specific context
        -- request metadata, filled by the app middleware after the response:
        latency_ms   REAL,
        client       TEXT,
        status       INTEGER,
        path         TEXT,
        -- ground truth, attached later via feedback (decoupled from scoring):
        ground_truth TEXT,               -- 'malicious' | 'benign' | NULL
        labeled_at   TEXT
    )
    """
)
_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TEXT    NOT NULL,
        method      TEXT,
        path        TEXT,
        client      TEXT,
        status      INTEGER,
        latency_ms  REAL
    )
    """
)
_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at     TEXT    NOT NULL,
        rule           TEXT    NOT NULL,   -- 'identity_burst' | 'ics_sustained' | 'high_severity'
        model          TEXT,
        subject        TEXT,
        severity       TEXT,               -- 'low' | 'medium' | 'high'
        window_seconds INTEGER,
        verdict_count  INTEGER,
        verdict_ids    TEXT,               -- JSON list of contributing verdict ids
        detail         TEXT,               -- JSON
        status         TEXT    NOT NULL DEFAULT 'open',
        priority       INTEGER,            -- 1-5 (5=most urgent); default from severity
        disposition    TEXT,               -- LLM advisory: escalate|monitor|likely_false_positive
        rationale      TEXT                -- LLM advisory rationale
    )
    """
)
_conn.execute("CREATE INDEX IF NOT EXISTS idx_a_rule_subject ON alerts(rule, subject, id)")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_a_status ON alerts(status, id)")
_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS actions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at  TEXT    NOT NULL,
        alert_id    INTEGER NOT NULL,
        action_type TEXT    NOT NULL,   -- 'log' | 'ticket' | 'webhook'
        status      TEXT    NOT NULL,   -- 'ok' | 'failed' | 'skipped'
        detail      TEXT                -- JSON
    )
    """
)
_conn.execute("CREATE INDEX IF NOT EXISTS idx_act_alert ON actions(alert_id, id)")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_v_model_id ON verdicts(model, id)")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_v_subject_id ON verdicts(subject, id)")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_v_flagged_id ON verdicts(flagged, id)")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_v_gt ON verdicts(ground_truth)")


def _ensure_columns():
    """Add any columns missing from a pre-existing DB (forward migration for stores
    created by an earlier schema); a no-op for a freshly created DB."""
    have = {r[1] for r in _conn.execute("PRAGMA table_info(verdicts)")}
    for col, decl in [("latency_ms", "REAL"), ("client", "TEXT"), ("status", "INTEGER"),
                      ("path", "TEXT"), ("ground_truth", "TEXT"), ("labeled_at", "TEXT")]:
        if col not in have:
            _conn.execute(f"ALTER TABLE verdicts ADD COLUMN {col} {decl}")
    have_a = {r[1] for r in _conn.execute("PRAGMA table_info(alerts)")}
    for col, decl in [("priority", "INTEGER"), ("disposition", "TEXT"), ("rationale", "TEXT")]:
        if col not in have_a:
            _conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {decl}")


_ensure_columns()
_conn.commit()

_VCOLS = ["id", "recorded_at", "event_time", "model", "subject", "flagged", "score",
          "detail", "latency_ms", "client", "status", "path", "ground_truth", "labeled_at"]

# ground-truth label normalization — accept the vocabulary any client might send
_MALICIOUS = {"malicious", "attack", "anomaly", "anomalous", "suspicious", "positive", "true", "1"}
_BENIGN = {"benign", "normal", "ok", "clean", "negative", "false", "0"}


# --- FIFO retention -------------------------------------------------------------------
# Bound each high-volume log table to a maximum row count, evicting the OLDEST rows first
# (FIFO), so the live-monitoring trail cannot grow without limit. Caps are env-configurable;
# 0/negative = unbounded. Trimming is batched (every RETENTION_TRIM_EVERY inserts) to amortize
# cost, so a table may transiently exceed its cap by up to that many rows. The metrics/Decide
# layers see the most recent window, which is far smaller than any cap, so eviction never
# affects live detection or alerting.
def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


MAX_VERDICTS = _int_env("MAX_VERDICTS", 100000)
MAX_REQUESTS = _int_env("MAX_REQUESTS", 100000)
MAX_ACTIONS = _int_env("MAX_ACTIONS", 50000)
RETENTION_TRIM_EVERY = _int_env("RETENTION_TRIM_EVERY", 100)
_ins_since_trim: dict = {"verdicts": 0, "requests": 0, "actions": 0}


def _trim_locked(table: str, cap: int) -> None:
    """Delete oldest rows so `table` keeps at most `cap` rows (FIFO by autoincrement id).
    Assumes the lock is held; the caller commits."""
    if cap and cap > 0:
        _conn.execute(
            f"DELETE FROM {table} WHERE id <= (SELECT COALESCE(MAX(id), 0) FROM {table}) - ?",
            (cap,),
        )


def _auto_trim_locked(table: str, cap: int) -> None:
    """Batched FIFO trim invoked on insert — trims once every RETENTION_TRIM_EVERY inserts."""
    _ins_since_trim[table] = _ins_since_trim.get(table, 0) + 1
    if _ins_since_trim[table] >= RETENTION_TRIM_EVERY:
        _ins_since_trim[table] = 0
        _trim_locked(table, cap)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def normalize_ground_truth(value: str) -> str:
    v = str(value).strip().lower()
    if v in _MALICIOUS:
        return "malicious"
    if v in _BENIGN:
        return "benign"
    raise ValueError(f"unrecognized ground_truth '{value}' "
                     f"(expected one of malicious/benign or a known synonym)")


# ------------------------------------------------------------------ writes
def record_verdict(model: str, flagged: bool, score: Optional[float],
                   subject: Optional[str] = None, event_time: Any = None,
                   detail: Optional[dict] = None) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO verdicts (recorded_at, event_time, model, subject, flagged, score, detail) "
            "VALUES (?,?,?,?,?,?,?)",
            (_now(), _iso(event_time), model, subject, int(bool(flagged)),
             None if score is None else float(score),
             json.dumps(detail) if detail is not None else None),
        )
        _auto_trim_locked("verdicts", MAX_VERDICTS)
        _conn.commit()
        return cur.lastrowid


def record_verdict_safe(*args, **kwargs) -> Optional[int]:
    """record_verdict that never raises — the Record layer must not break scoring."""
    try:
        return record_verdict(*args, **kwargs)
    except Exception:
        return None


def update_verdict_meta(verdict_id: int, latency_ms: Optional[float] = None,
                        status: Optional[int] = None, client: Optional[str] = None,
                        path: Optional[str] = None) -> None:
    """Attach request metadata (from the middleware) to an already-recorded verdict."""
    try:
        with _lock:
            _conn.execute(
                "UPDATE verdicts SET latency_ms=?, status=?, client=?, path=? WHERE id=?",
                (latency_ms, status, client, path, verdict_id),
            )
            _conn.commit()
    except Exception:
        pass


def record_request(method: str, path: str, client: Optional[str],
                   status: Optional[int], latency_ms: Optional[float]) -> Optional[int]:
    """Audit a non-scored request (health check, error, validation failure, etc.)."""
    try:
        with _lock:
            cur = _conn.execute(
                "INSERT INTO requests (recorded_at, method, path, client, status, latency_ms) "
                "VALUES (?,?,?,?,?,?)",
                (_now(), method, path, client, status, latency_ms),
            )
            _auto_trim_locked("requests", MAX_REQUESTS)
            _conn.commit()
            return cur.lastrowid
    except Exception:
        return None


def set_ground_truth(verdict_id: int, ground_truth: str) -> bool:
    """Attach the true label to a recorded verdict (the feedback loop). Returns whether
    a row was updated. Raises ValueError on an unrecognized label."""
    gt = normalize_ground_truth(ground_truth)
    with _lock:
        cur = _conn.execute(
            "UPDATE verdicts SET ground_truth=?, labeled_at=? WHERE id=?",
            (gt, _now(), verdict_id),
        )
        _conn.commit()
        return cur.rowcount > 0


# ------------------------------------------------------------------ reads
def _rows_to_dicts(rows):
    out = []
    for r in rows:
        d = dict(zip(_VCOLS, r))
        d["flagged"] = bool(d["flagged"])
        if d.get("detail"):
            d["detail"] = json.loads(d["detail"])
        out.append(d)
    return out


def query_verdicts(model: Optional[str] = None, subject: Optional[str] = None,
                   flagged: Optional[bool] = None, labeled: Optional[bool] = None,
                   limit: int = 100) -> list[dict]:
    q = f"SELECT {', '.join(_VCOLS)} FROM verdicts"
    conds, args = [], []
    if model is not None:
        conds.append("model = ?"); args.append(model)
    if subject is not None:
        conds.append("subject = ?"); args.append(subject)
    if flagged is not None:
        conds.append("flagged = ?"); args.append(int(flagged))
    if labeled is True:
        conds.append("ground_truth IS NOT NULL")
    elif labeled is False:
        conds.append("ground_truth IS NULL")
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC LIMIT ?"; args.append(int(limit))
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    return _rows_to_dicts(rows)


def max_verdict_id() -> int:
    with _lock:
        return _conn.execute("SELECT COALESCE(MAX(id), 0) FROM verdicts").fetchone()[0]


def verdicts_since(after_id: int, limit: int = 200) -> list[dict]:
    """Verdicts with id > after_id, oldest-first — the incremental feed for the live dashboard's
    SSE stream."""
    q = f"SELECT {', '.join(_VCOLS)} FROM verdicts WHERE id > ? ORDER BY id ASC LIMIT ?"
    with _lock:
        rows = _conn.execute(q, (int(after_id), int(limit))).fetchall()
    return _rows_to_dicts(rows)


def query_requests(limit: int = 100) -> list[dict]:
    cols = ["id", "recorded_at", "method", "path", "client", "status", "latency_ms"]
    with _lock:
        rows = _conn.execute(
            f"SELECT {', '.join(cols)} FROM requests ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def enforce_retention(max_verdicts: Optional[int] = None, max_requests: Optional[int] = None,
                      max_actions: Optional[int] = None) -> dict:
    """Immediately trim the high-volume log tables to their caps (FIFO, oldest evicted). Uses the
    env-configured caps unless overridden. Returns per-table before/after/evicted counts. Run once
    at import so an already-oversized DB is bounded on startup."""
    caps = {"verdicts": MAX_VERDICTS if max_verdicts is None else max_verdicts,
            "requests": MAX_REQUESTS if max_requests is None else max_requests,
            "actions": MAX_ACTIONS if max_actions is None else max_actions}
    out = {}
    with _lock:
        for table, cap in caps.items():
            before = _conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            _trim_locked(table, cap)
            after = _conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            out[table] = {"cap": cap, "before": before, "after": after, "evicted": before - after}
        _conn.commit()
    return out


def stats() -> dict:
    with _lock:
        total = _conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0]
        flagged = _conn.execute("SELECT COUNT(*) FROM verdicts WHERE flagged=1").fetchone()[0]
        labeled = _conn.execute("SELECT COUNT(*) FROM verdicts WHERE ground_truth IS NOT NULL").fetchone()[0]
        reqs = _conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        by = _conn.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(flagged),0) FROM verdicts GROUP BY model"
        ).fetchall()
    return {
        "verdicts": total, "flagged": flagged, "labeled": labeled,
        "audited_requests": reqs,
        "by_model": {m: {"count": c, "flagged": int(f)} for m, c, f in by},
        "retention": {"max_verdicts": MAX_VERDICTS, "max_requests": MAX_REQUESTS,
                      "max_actions": MAX_ACTIONS, "trim_every": RETENTION_TRIM_EVERY},
        "db_path": str(DB_PATH),
    }


# Bound an already-large DB on startup (FIFO), so restarting the backend enforces the caps.
enforce_retention()


def metrics(model: Optional[str] = None) -> dict:
    """Confusion matrix + precision/recall/specificity over labelled verdicts —
    comparing the model's flagged decision against the attached ground truth."""
    q = "SELECT flagged, ground_truth FROM verdicts WHERE ground_truth IS NOT NULL"
    args = []
    if model is not None:
        q += " AND model = ?"; args.append(model)
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    tp = fp = fn = tn = 0
    for flagged, gt in rows:
        malicious = (gt == "malicious")
        if flagged and malicious:
            tp += 1
        elif flagged and not malicious:
            fp += 1
        elif (not flagged) and malicious:
            fn += 1
        else:
            tn += 1

    def _safe(n, d):
        return round(n / d, 4) if d else None

    return {
        "model": model or "all", "labeled": len(rows),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": _safe(tp, tp + fp),
        "recall": _safe(tp, tp + fn),
        "specificity": _safe(tn, tn + fp),
        "accuracy": _safe(tp + tn, len(rows)),
    }


# ------------------------------------------------------------------ Decide layer (C2)
_ACOLS = ["id", "created_at", "rule", "model", "subject", "severity", "window_seconds",
          "verdict_count", "verdict_ids", "detail", "status", "priority", "disposition", "rationale"]

# deterministic default priority from severity (1-5, 5 = most urgent), set at alert creation
_SEVERITY_PRIORITY = {"high": 4, "medium": 2, "low": 1}


def recent_verdicts(since_iso: str, model: Optional[str] = None,
                    flagged_only: bool = True) -> list[dict]:
    """Verdicts recorded at/after since_iso (ISO-8601 UTC), oldest first — the window the
    policy rules evaluate over."""
    q = ("SELECT id, recorded_at, model, subject, flagged, score, ground_truth "
         "FROM verdicts WHERE recorded_at >= ?")
    args: list = [since_iso]
    if model is not None:
        q += " AND model = ?"; args.append(model)
    if flagged_only:
        q += " AND flagged = 1"
    q += " ORDER BY id ASC"
    cols = ["id", "recorded_at", "model", "subject", "flagged", "score", "ground_truth"]
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(zip(cols, r)); d["flagged"] = bool(d["flagged"]); out.append(d)
    return out


def subject_outcome_history(subject: Optional[str], model: Optional[str] = None) -> dict:
    """How a subject's past flagged verdicts actually turned out (labelled ground truth):
    lets the policy escalate confirmed-bad subjects and suppress chronic false positives."""
    h = {"malicious": 0, "benign": 0}
    if subject is None:
        return h
    q = "SELECT ground_truth, COUNT(*) FROM verdicts WHERE subject = ? AND ground_truth IS NOT NULL"
    args: list = [subject]
    if model is not None:
        q += " AND model = ?"; args.append(model)
    q += " GROUP BY ground_truth"
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    for gt, n in rows:
        if gt in h:
            h[gt] = n
    return h


def recent_alert_exists(rule: str, subject: Optional[str], since_iso: str) -> bool:
    """Whether an alert (ANY status) for this (rule, subject) already exists within the
    window. Dedup makes evaluate() idempotent, and — by counting closed alerts too — an
    analyst's close stays sticky for the window instead of immediately re-firing on
    continued activity."""
    q = "SELECT 1 FROM alerts WHERE rule = ? AND created_at >= ?"
    args: list = [rule, since_iso]
    if subject is None:
        q += " AND subject IS NULL"
    else:
        q += " AND subject = ?"; args.append(subject)
    q += " LIMIT 1"
    with _lock:
        return _conn.execute(q, args).fetchone() is not None


def record_alert(rule: str, model: Optional[str], subject: Optional[str], severity: str,
                 window_seconds: int, verdict_ids: list, detail: Optional[dict] = None) -> int:
    priority = _SEVERITY_PRIORITY.get(severity, 2)  # deterministic default; LLM may refine later
    with _lock:
        cur = _conn.execute(
            "INSERT INTO alerts (created_at, rule, model, subject, severity, window_seconds, "
            "verdict_count, verdict_ids, detail, status, priority) "
            "VALUES (?,?,?,?,?,?,?,?,?, 'open', ?)",
            (_now(), rule, model, subject, severity, window_seconds, len(verdict_ids),
             json.dumps(verdict_ids), json.dumps(detail) if detail is not None else None, priority),
        )
        _conn.commit()
        return cur.lastrowid


def set_disposition(alert_id: int, priority: int, disposition: Optional[str],
                    rationale: Optional[str]) -> bool:
    """Store the LLM's advisory prioritization on an alert (from ai_triage.assess)."""
    with _lock:
        cur = _conn.execute(
            "UPDATE alerts SET priority = ?, disposition = ?, rationale = ? WHERE id = ?",
            (priority, disposition, rationale, alert_id),
        )
        _conn.commit()
        return cur.rowcount > 0


def query_alerts(status: Optional[str] = None, model: Optional[str] = None,
                 limit: int = 100) -> list[dict]:
    q = f"SELECT {', '.join(_ACOLS)} FROM alerts"
    conds, args = [], []
    if status is not None:
        conds.append("status = ?"); args.append(status)
    if model is not None:
        conds.append("model = ?"); args.append(model)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY COALESCE(priority, 0) DESC, id DESC LIMIT ?"; args.append(int(limit))
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_ACOLS, r))
        if d.get("verdict_ids"):
            d["verdict_ids"] = json.loads(d["verdict_ids"])
        if d.get("detail"):
            d["detail"] = json.loads(d["detail"])
        out.append(d)
    return out


def get_alert(alert_id: int) -> Optional[dict]:
    with _lock:
        rows = _conn.execute(
            f"SELECT {', '.join(_ACOLS)} FROM alerts WHERE id = ?", (alert_id,)).fetchall()
    if not rows:
        return None
    d = dict(zip(_ACOLS, rows[0]))
    if d.get("verdict_ids"):
        d["verdict_ids"] = json.loads(d["verdict_ids"])
    if d.get("detail"):
        d["detail"] = json.loads(d["detail"])
    return d


def close_alert(alert_id: int) -> bool:
    with _lock:
        cur = _conn.execute("UPDATE alerts SET status = 'closed' WHERE id = ?", (alert_id,))
        _conn.commit()
        return cur.rowcount > 0


# ------------------------------------------------------------------ Act layer (C3)
_ACTCOLS = ["id", "created_at", "alert_id", "action_type", "status", "detail"]


def record_action(alert_id: int, action_type: str, status: str,
                  detail: Optional[dict] = None) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO actions (created_at, alert_id, action_type, status, detail) "
            "VALUES (?,?,?,?,?)",
            (_now(), alert_id, action_type, status,
             json.dumps(detail) if detail is not None else None),
        )
        _auto_trim_locked("actions", MAX_ACTIONS)
        _conn.commit()
        return cur.lastrowid


def query_actions(alert_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    q = f"SELECT {', '.join(_ACTCOLS)} FROM actions"
    args: list = []
    if alert_id is not None:
        q += " WHERE alert_id = ?"; args.append(alert_id)
    q += " ORDER BY id DESC LIMIT ?"; args.append(int(limit))
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_ACTCOLS, r))
        if d.get("detail"):
            d["detail"] = json.loads(d["detail"])
        out.append(d)
    return out
