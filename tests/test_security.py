"""Security tests: authentication, authorisation, IDOR, business logic, input validation, Host header.
These are exactly the categories checked by Aikido's AI Code Audit."""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from tests.conftest import PASSWORD, login


# ---------------------------------------------------------------- Host header injection (Aikido finding)
def test_malicious_host_header_rejected(client):
    for host in ("evil.com", "localhost/admin?", "testserver/api/advisor/metrics#", "testserver@evil.com"):
        r = client.get("/api/health", headers={"Host": host})
        assert r.status_code == 400, host


def test_security_decisions_do_not_use_request_url():
    """The middleware must rely on the ASGI scope path, never on request.url (rebuilt from Host)."""
    import inspect

    from app import main
    src = inspect.getsource(main.security_middleware)
    assert "request.url" not in src and 'scope.get("path"' in src


def test_patched_starlette_version():
    import starlette
    major, minor, patch = (int(x) for x in starlette.__version__.split(".")[:3])
    assert (major, minor, patch) >= (1, 0, 1)


# ---------------------------------------------------------------- Authentication
def test_login_wrong_password_and_unknown_user_look_identical(client):
    a = client.post("/api/auth/login", json={"username": "emma", "password": "nope"})
    b = client.post("/api/auth/login", json={"username": "ghost", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_login_rate_limited(client):
    for _ in range(settings.login_max_attempts):
        client.post("/api/auth/login", json={"username": "thomas", "password": "wrong"})
    r = client.post("/api/auth/login", json={"username": "thomas", "password": PASSWORD})
    assert r.status_code == 429


def test_endpoints_require_token(client):
    assert client.get("/api/me/feed").status_code == 401
    assert client.get("/api/advisor/metrics").status_code == 401
    assert client.get("/api/me/appointments").status_code == 401


def test_forged_tokens_rejected(client):
    now = datetime.now(timezone.utc)
    claims = {"sub": "emma", "role": "customer", "cid": "c_001", "iat": now, "exp": now + timedelta(minutes=5)}
    wrong_key = jwt.encode(claims, "not-the-server-key-" * 3, algorithm="HS256")
    none_alg = jwt.encode(claims, key="", algorithm="none")
    expired = jwt.encode({**claims, "exp": now - timedelta(minutes=1)}, settings.secret_key, algorithm="HS256")
    for tok in (wrong_key, none_alg, expired):
        assert client.get("/api/me/feed", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_token_cannot_escalate_role_or_switch_customer(client):
    now = datetime.now(timezone.utc)
    for claims in ({"sub": "emma", "role": "advisor", "cid": "c_001"}, {"sub": "emma", "role": "customer", "cid": "c_002"}):
        tok = jwt.encode({**claims, "iat": now, "exp": now + timedelta(minutes=5)}, settings.secret_key, algorithm="HS256")
        assert client.get("/api/me/feed", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_deleted_user_token_revoked(client, conn):
    h = login(client, "emma")
    conn.execute("DELETE FROM users WHERE username = 'emma'")
    conn.commit()
    assert client.get("/api/me/feed", headers=h).status_code == 401


# ---------------------------------------------------------------- Authorisation by role
def test_customer_cannot_use_advisor_endpoints(client):
    h = login(client, "emma")
    assert client.get("/api/advisor/metrics", headers=h).status_code == 403
    assert client.get("/api/advisor/tasks", headers=h).status_code == 403
    assert client.post("/api/advisor/tasks/1/actions", headers=h, json={"action": "dismiss", "note": "x"}).status_code == 403


def test_advisor_has_no_customer_view(client):
    h = login(client, "advisor")
    assert client.get("/api/me/feed", headers=h).status_code == 403
    assert client.post("/api/me/appointments", headers=h, json={"decision_id": "a" * 32, "slot_id": 1, "mode": "phone"}).status_code == 403


# ---------------------------------------------------------------- IDOR
def test_idor_on_every_decision_endpoint(client):
    emma, sofia = login(client, "emma"), login(client, "sofia")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/cta", headers=sofia, json={"cta_id": "start_review"}).status_code == 404
    assert client.post(f"/api/me/decisions/{did}/feedback", headers=sofia, json={"reaction": "never"}).status_code == 404
    assert client.post(f"/api/me/decisions/{did}/why", headers=sofia).status_code == 404
    assert client.get(f"/api/me/decisions/{did}/voice", headers=sofia).status_code == 404
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": 1, "mode": "phone"}).status_code == 404
    assert client.post(f"/api/me/decisions/{did}/cta", headers=emma, json={"cta_id": "start_review"}).status_code == 200


def test_cannot_cancel_someone_elses_appointment(client):
    sofia, emma = login(client, "sofia"), login(client, "emma")
    did = client.get("/api/me/feed", headers=sofia).json()["decision_id"]
    slot = client.get("/api/me/slots", headers=sofia).json()[0]["id"]
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": slot, "mode": "phone"}).status_code == 200
    appt = client.get("/api/me/appointments", headers=sofia).json()[0]["id"]
    assert client.post(f"/api/me/appointments/{appt}/cancel", headers=emma).status_code == 404
    assert client.get("/api/me/appointments", headers=emma).json() == []
    assert client.post(f"/api/me/appointments/{appt}/cancel", headers=sofia).status_code == 200


def test_consent_and_language_only_change_own_data(client, conn):
    emma = login(client, "emma")
    client.put("/api/me/consents/digital", headers=emma, json={"enabled": False})
    client.put("/api/me/language", headers=emma, json={"language": "nl"})
    assert {r["customer_id"] for r in conn.execute("SELECT customer_id FROM consents")} == {"c_001"}
    langs = dict(conn.execute("SELECT id, language FROM customers WHERE id IN ('c_001','c_002')").fetchall())
    assert langs == {"c_001": "nl", "c_002": "en"}


def test_no_endpoint_accepts_customer_id(client):
    emma = login(client, "emma")
    r = client.get("/api/me/feed?customer_id=c_002", headers=emma)
    assert r.json()["screen"]["action_id"] == "family_insurance_review"


# ---------------------------------------------------------------- Business logic
def test_cannot_trigger_cta_of_another_action(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/cta", headers=emma, json={"cta_id": "confirm_transfer"}).status_code == 404


def test_scam_hold_cannot_be_bypassed(client, conn):
    marcel = login(client, "marcel")
    did = client.get("/api/me/feed", headers=marcel).json()["decision_id"]
    r = client.post(f"/api/me/decisions/{did}/cta", headers=marcel, json={"cta_id": "confirm_transfer"})
    assert r.status_code == 409
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id='c_004'").fetchone()[0] == "held"
    assert client.post(f"/api/me/decisions/{did}/cta", headers=marcel, json={"cta_id": "cancel_transfer"}).status_code == 200
    conn.commit()
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id='c_004'").fetchone()[0] == "cancelled"


def test_client_cannot_self_report_completed(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/feedback", headers=emma, json={"reaction": "completed"}).status_code == 422


def test_feedback_on_abstention_refused(client):
    thomas = login(client, "thomas")
    did = client.get("/api/me/feed", headers=thomas).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/feedback", headers=thomas, json={"reaction": "not_now"}).status_code == 409


def test_booking_rules(client):
    sofia, thomas, yasmine = login(client, "sofia"), login(client, "thomas"), login(client, "yasmine")
    did = client.get("/api/me/feed", headers=sofia).json()["decision_id"]
    slots = client.get("/api/me/slots", headers=sofia).json()
    # a message without an appointment offer cannot be used to book
    tdid = client.get("/api/me/feed", headers=thomas).json()["decision_id"]
    assert client.post("/api/me/appointments", headers=thomas, json={"decision_id": tdid, "slot_id": slots[0]["id"], "mode": "phone"}).status_code == 409
    ydid = client.get("/api/me/feed", headers=yasmine).json()["decision_id"]
    assert client.post("/api/me/appointments", headers=yasmine, json={"decision_id": ydid, "slot_id": slots[0]["id"], "mode": "phone"}).status_code == 409
    # unknown slot, bad mode
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": 99999, "mode": "phone"}).status_code == 404
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": slots[0]["id"], "mode": "teleport"}).status_code == 422
    # one active appointment per customer
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": slots[0]["id"], "mode": "video"}).status_code == 200
    assert client.post("/api/me/appointments", headers=sofia, json={"decision_id": did, "slot_id": slots[1]["id"], "mode": "video"}).status_code == 409
    # a taken slot disappears from the list
    assert slots[0]["id"] not in [s["id"] for s in client.get("/api/me/slots", headers=sofia).json()]


def test_double_booking_blocked_by_database(conn):
    """Even if two requests race past the code checks, the partial unique index refuses the second booking."""
    import sqlite3

    import pytest
    conn.execute("INSERT INTO appointments(customer_id, slot_id, action_id, mode, created_at, created_by) VALUES ('c_001', 1, 'x', 'phone', 'now', 't')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO appointments(customer_id, slot_id, action_id, mode, created_at, created_by) VALUES ('c_002', 1, 'x', 'phone', 'now', 't')")


def test_advisor_actions_must_match_task_type(client):
    sofia = login(client, "sofia")
    client.get("/api/me/feed", headers=sofia)                      # creates an outreach task
    adv = login(client, "advisor")
    task = client.get("/api/advisor/tasks", headers=adv).json()[0]
    assert task["task_type"] == "outreach"
    tid = task["id"]
    # actions of another task type are refused
    assert client.post(f"/api/advisor/tasks/{tid}/actions", headers=adv, json={"action": "release_transfer", "note": "x"}).status_code == 409
    assert client.post(f"/api/advisor/tasks/{tid}/actions", headers=adv, json={"action": "complete", "note": "x"}).status_code == 409
    # a note is required to dismiss; unknown action rejected by the schema
    assert client.post(f"/api/advisor/tasks/{tid}/actions", headers=adv, json={"action": "dismiss"}).status_code == 409
    assert client.post(f"/api/advisor/tasks/{tid}/actions", headers=adv, json={"action": "delete_customer"}).status_code == 422
    assert client.post("/api/advisor/tasks/9999/actions", headers=adv, json={"action": "dismiss", "note": "x"}).status_code == 404


def test_advisor_journal_requires_a_task(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    adv = login(client, "advisor")
    assert client.get(f"/api/advisor/decisions/{did}", headers=adv).status_code == 404
    slot = client.get("/api/me/slots", headers=emma).json()[0]["id"]
    client.post("/api/me/appointments", headers=emma, json={"decision_id": did, "slot_id": slot, "mode": "branch"})
    assert client.get(f"/api/advisor/decisions/{did}", headers=adv).status_code == 200


# ---------------------------------------------------------------- Input validation and headers
def test_strict_input_validation(client):
    emma = login(client, "emma")
    assert client.post("/api/auth/login", json={"username": "emma", "password": PASSWORD, "role": "advisor"}).status_code == 422
    assert client.post("/api/auth/login", json={"username": "emma' OR 1=1--", "password": "x"}).status_code == 422
    assert client.post("/api/me/decisions/not-a-uuid/cta", headers=emma, json={"cta_id": "start_review"}).status_code == 422
    assert client.put("/api/me/consents/unknownfam", headers=emma, json={"enabled": False}).status_code == 404
    assert client.put("/api/me/consents/digital", headers=emma, json={"enabled": False, "customer_id": "c_002"}).status_code == 422
    assert client.put("/api/me/language", headers=emma, json={"language": "de"}).status_code == 422


def test_body_size_limit(client):
    r = client.post("/api/auth/login", content=b"{" + b" " * 20000 + b"}", headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_security_headers(client):
    r = client.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
