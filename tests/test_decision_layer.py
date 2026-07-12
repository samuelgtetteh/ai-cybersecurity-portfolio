"""End-to-end tests for the decision layer (Track C: Record -> Decide -> Act), driven
through FastAPI's TestClient so they exercise the real store, policy rules, and responders.

Isolation: conftest.py points VERDICT_DB at a throwaway DB, and every test uses a UNIQUE
subject name, so assertions are about that test's own activity and are unaffected by other
tests writing to the shared throwaway trail.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import app
    return TestClient(app.app)


def _login(client, user, pc, suspicious=True):
    """Post one login. 'suspicious' uses an unknown auth type + failed remote-interactive,
    the pattern the detector treats as anomalous once access breadth builds up."""
    return client.post("/identity/score", json={
        "src_user": user, "src_pc": pc,
        "auth_type": "TotallyUnrecognizedAuth" if suspicious else "Kerberos",
        "logon_type": "RemoteInteractive" if suspicious else "Network",
        "orientation": "LogOn", "success": "Fail" if suspicious else "Success",
    })


# --- C1: Record + X-Verdict-Id + feedback + metrics ----------------------

def test_score_records_verdict_and_returns_id(client):
    r = _login(client, "test-solo@DOM1", "C1", suspicious=False)
    assert r.status_code == 200
    vid = r.headers.get("X-Verdict-Id")
    assert vid is not None                       # every scored response carries the id
    got = client.get("/decision/verdicts?subject=test-solo@DOM1&limit=1").json()
    assert got and got[0]["subject"] == "test-solo@DOM1"
    # request metadata was enriched by the middleware
    assert got[0]["path"] == "/identity/score" and got[0]["status"] == 200


def test_feedback_attaches_ground_truth_and_metrics(client):
    r = _login(client, "test-fb@DOM1", "C1", suspicious=True)
    vid = r.headers["X-Verdict-Id"]
    ok = client.post(f"/decision/verdicts/{vid}/feedback", json={"ground_truth": "malicious"})
    assert ok.status_code == 200
    # unknown label is rejected; unknown id is 404
    assert client.post(f"/decision/verdicts/{vid}/feedback",
                       json={"ground_truth": "purple"}).status_code == 422
    assert client.post("/decision/verdicts/999999/feedback",
                       json={"ground_truth": "benign"}).status_code == 404
    m = client.get("/decision/metrics").json()
    assert m["labeled"] >= 1
    for k in ("tp", "fp", "fn", "tn"):
        assert k in m


def test_non_scored_request_is_audited(client):
    client.get("/health")
    reqs = client.get("/decision/requests?limit=50").json()
    assert any(x["path"] == "/health" for x in reqs)


# --- C2: Decide (rules -> alerts) ----------------------------------------

BURST_USER = "test-burst@DOM1"


def test_identity_burst_raises_alert(client):
    for i in range(12):
        _login(client, BURST_USER, f"C90{i:02d}", suspicious=True)
    client.post("/decision/evaluate")
    alerts = client.get("/decision/alerts?limit=500&auto_evaluate=false").json()
    mine = [a for a in alerts if a["rule"] == "identity_burst" and a["subject"] == BURST_USER]
    assert mine, "expected an identity_burst alert for the burst subject"
    assert mine[0]["severity"] in ("low", "medium", "high")
    assert mine[0]["verdict_count"] >= 3


def test_evaluate_is_idempotent(client):
    # a second evaluate over the same window must not duplicate the burst alert
    client.post("/decision/evaluate")
    alerts = client.get("/decision/alerts?limit=500&auto_evaluate=false").json()
    mine = [a for a in alerts if a["rule"] == "identity_burst" and a["subject"] == BURST_USER]
    assert len(mine) == 1


def test_benign_history_suppresses_burst(client):
    # a subject whose flagged logins are consistently labelled benign is a chronic false
    # positive: its burst should be suppressed by the outcome-weighting rule.
    user = "test-suppress@DOM1"
    for i in range(12):
        r = _login(client, user, f"C95{i:02d}", suspicious=True)
        vid = r.headers.get("X-Verdict-Id")
        if vid:
            client.post(f"/decision/verdicts/{vid}/feedback", json={"ground_truth": "benign"})
    client.post("/decision/evaluate")
    alerts = client.get("/decision/alerts?limit=500&auto_evaluate=false").json()
    mine = [a for a in alerts if a["rule"] == "identity_burst" and a["subject"] == user]
    assert not mine, "burst from a chronic-benign subject should be suppressed"


# --- C3: Act (responders + lifecycle) ------------------------------------

def test_actions_fired_for_alert_and_close(client):
    # reuse the burst alert from the C2 test's subject
    alerts = client.get("/decision/alerts?limit=500&auto_evaluate=false").json()
    mine = [a for a in alerts if a["rule"] == "identity_burst" and a["subject"] == BURST_USER]
    assert mine
    aid = mine[0]["id"]
    acts = client.get(f"/decision/actions?alert_id={aid}").json()
    types = {a["action_type"] for a in acts}
    assert {"log", "ticket"}.issubset(types)          # high severity routes log + ticket
    assert all(a["status"] in ("ok", "skipped", "failed") for a in acts)
    # webhook is present but skipped when ACTION_WEBHOOK_URL is unset
    wh = [a for a in acts if a["action_type"] == "webhook"]
    assert wh and wh[0]["status"] == "skipped"
    # close the alert (analyst resolution) + 404 on unknown id
    assert client.post(f"/decision/alerts/{aid}/close").json()["status"] == "closed"
    assert client.post("/decision/alerts/999999/close").status_code == 404
    # closed alert no longer appears in the open queue
    open_ids = [a["id"] for a in client.get("/decision/alerts?status=open&auto_evaluate=false").json()]
    assert aid not in open_ids
