"""
Tests for the Compliance Advisor API (control-advisor wrapped over HTTP). Runs on a minimal app
carrying only the advisor router (no heavy model load). Scanning + the embedder are stubbed; the
real prioritization + DOCX/XLSX/JSON report builders are exercised end to end (no LLM).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import advisor_api as A


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(A.router)
    return TestClient(app)


def test_health_available(client):
    h = client.get("/advisor/health").json()
    assert h["available"] is True


def test_base_questions(client):
    d = client.get("/advisor/questions").json()
    ids = [q["id"] for q in d["questions"]]
    assert ids == ["sector", "regulated_data", "internet_facing", "maturity"]
    assert d["business_name"]["type"] == "text"
    # regulated_data is multi-select and carries option descriptions
    rd = next(q for q in d["questions"] if q["id"] == "regulated_data")
    assert rd["multi"] is True and len(rd["options"]) >= 2


def test_followups_are_adaptive_subset(client):
    allids = {q["id"] for q in A.ca_interview.FOLLOWUP_QUESTIONS}
    r = client.post("/advisor/followups", json={
        "answers": {"sector": "healthcare", "regulated_data": ["phi"], "internet_facing": "yes"},
        "categories": ["database", "web", "remote_access"]})
    ids = [q["id"] for q in r.json()["questions"]]
    assert set(ids) <= allids                       # only real follow-ups, evaluated server-side
    if ids:                                          # answering one removes it from the next batch
        one = ids[0]
        r2 = client.post("/advisor/followups", json={
            "answers": {"regulated_data": ["phi"], one: "yes"},
            "categories": ["database", "web", "remote_access"]})
        assert one not in [q["id"] for q in r2.json()["questions"]]


def test_scan_maps_controls_and_authz(client, monkeypatch):
    fake_scan = {"cidr": "127.0.0.1/32", "hosts_found": 1,
                 "results": [{"ip": "127.0.0.1", "categories": ["web"]}]}
    fake_rec = {"cidr": "127.0.0.1/32", "hosts": [
        {"ip": "127.0.0.1", "categories": ["web"],
         "recommended_controls": {"web": [{"control_id": "SC-7", "control_text": "x", "score": 0.8}]}}]}
    monkeypatch.setattr(A.network_scan, "scan", lambda *a, **k: fake_scan)
    monkeypatch.setattr(A.control_mapper, "recommend_for_scan", lambda sr, top_k=3: fake_rec)
    r = client.post("/advisor/scan", json={"target": "127.0.0.1"})
    assert r.status_code == 200
    assert r.json()["recommendations"]["hosts"][0]["ip"] == "127.0.0.1"
    # a public target is refused before any scan happens
    monkeypatch.delenv("SCAN_ALLOW_ANY", raising=False)
    assert client.post("/advisor/scan", json={"target": "8.8.8.8"}).status_code == 403


def test_report_generation_and_download(client, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "REPORTS_DIR", tmp_path)
    scan_report = {"cidr": "192.168.0.0/30", "hosts_found": 1, "results": [
        {"ip": "192.168.0.2", "hostname": "web01", "mac_address": None, "vendor": None,
         "response_time_ms": 5, "open_ports": [80], "device_type_guess": "server",
         "services": [{"port": 80, "service": "http", "category": "web"}], "categories": ["web"]}]}
    rec = {"cidr": "192.168.0.0/30", "hosts": [
        {"ip": "192.168.0.2", "categories": ["web"],
         "recommended_controls": {"web": [{"control_id": "SC-7",
                                           "control_text": "Boundary protection", "score": 0.82}]}}]}
    answers = {"business_name": "Acme Clinic", "sector": "healthcare", "regulated_data": ["phi"],
               "internet_facing": "yes", "maturity": "developing"}
    r = client.post("/advisor/report", json={"scan_report": scan_report, "recommendations": rec,
                                             "answers": answers, "with_language": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_used"] is False and isinstance(body["rows"], list)
    assert body["files"].get("docx") and body["files"].get("xlsx") and body["files"].get("json")
    rid = body["report_id"]
    for fmt in ("docx", "xlsx", "json"):
        d = client.get(f"/advisor/report/{rid}/{fmt}")
        assert d.status_code == 200 and len(d.content) > 100
    assert client.get(f"/advisor/report/{rid}/pdf").status_code == 404
