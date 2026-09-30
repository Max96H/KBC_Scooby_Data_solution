"""Tests de sécurité : authentification, autorisation, IDOR, logique métier, validation d'entrée.
Ce sont exactement les catégories vérifiées par l'AI Code Audit d'Aikido."""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from tests.conftest import PASSWORD, login


# ---------------------------------------------------------------- Authentification
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
    # Même signé avec la bonne clé, un token dont le rôle / client ne correspond pas au compte est refusé
    for claims in ({"sub": "emma", "role": "advisor", "cid": "c_001"}, {"sub": "emma", "role": "customer", "cid": "c_002"}):
        tok = jwt.encode({**claims, "iat": now, "exp": now + timedelta(minutes=5)}, settings.secret_key, algorithm="HS256")
        assert client.get("/api/me/feed", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_deleted_user_token_revoked(client, conn):
    h = login(client, "emma")
    conn.execute("DELETE FROM users WHERE username = 'emma'")
    conn.commit()
    assert client.get("/api/me/feed", headers=h).status_code == 401


# ---------------------------------------------------------------- Autorisation par rôle
def test_customer_cannot_use_advisor_endpoints(client):
    h = login(client, "emma")
    assert client.get("/api/advisor/metrics", headers=h).status_code == 403
    assert client.get("/api/advisor/tasks", headers=h).status_code == 403
    assert client.post("/api/advisor/tasks/1/done", headers=h).status_code == 403


def test_advisor_has_no_customer_view(client):
    h = login(client, "conseiller")
    assert client.get("/api/me/feed", headers=h).status_code == 403


# ---------------------------------------------------------------- IDOR
def test_idor_on_every_decision_endpoint(client):
    emma, sofia = login(client, "emma"), login(client, "sofia")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/cta", headers=sofia, json={"cta_id": "start_review"}).status_code == 404
    assert client.post(f"/api/me/decisions/{did}/feedback", headers=sofia, json={"reaction": "never"}).status_code == 404
    assert client.post(f"/api/me/decisions/{did}/why", headers=sofia).status_code == 404
    assert client.get(f"/api/me/decisions/{did}/voice", headers=sofia).status_code == 404
    # et la décision d'Emma n'a pas été modifiée
    assert client.post(f"/api/me/decisions/{did}/cta", headers=emma, json={"cta_id": "start_review"}).status_code == 200


def test_consent_only_changes_own_data(client, conn):
    emma = login(client, "emma")
    client.put("/api/me/consents/digital", headers=emma, json={"enabled": False})
    rows = conn.execute("SELECT customer_id FROM consents").fetchall()
    assert {r["customer_id"] for r in rows} == {"c_001"}


def test_no_endpoint_accepts_customer_id(client):
    emma = login(client, "emma")
    # un paramètre customer_id est simplement ignoré : l'identité vient du token
    r = client.get("/api/me/feed?customer_id=c_002", headers=emma)
    assert r.json()["screen"]["action_id"] == "family_insurance_review"


# ---------------------------------------------------------------- Logique métier
def test_cannot_trigger_cta_of_another_action(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    # confirm_transfer existe dans le catalogue, mais pas pour cette action
    assert client.post(f"/api/me/decisions/{did}/cta", headers=emma, json={"cta_id": "confirm_transfer"}).status_code == 404


def test_scam_hold_cannot_be_bypassed(client, conn):
    marcel = login(client, "marcel")
    did = client.get("/api/me/feed", headers=marcel).json()["decision_id"]
    r = client.post(f"/api/me/decisions/{did}/cta", headers=marcel, json={"cta_id": "confirm_transfer"})
    assert r.status_code == 409
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id='c_004'").fetchone()[0] == "held"
    r = client.post(f"/api/me/decisions/{did}/cta", headers=marcel, json={"cta_id": "cancel_transfer"})
    assert r.status_code == 200
    conn.commit()
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id='c_004'").fetchone()[0] == "cancelled"


def test_client_cannot_self_report_completed(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    r = client.post(f"/api/me/decisions/{did}/feedback", headers=emma, json={"reaction": "completed"})
    assert r.status_code == 422


def test_feedback_on_abstention_refused(client):
    thomas = login(client, "thomas")
    did = client.get("/api/me/feed", headers=thomas).json()["decision_id"]
    assert client.post(f"/api/me/decisions/{did}/feedback", headers=thomas, json={"reaction": "not_now"}).status_code == 409


# ---------------------------------------------------------------- Validation d'entrée et en-têtes
def test_strict_input_validation(client):
    emma = login(client, "emma")
    assert client.post("/api/auth/login", json={"username": "emma", "password": PASSWORD, "role": "advisor"}).status_code == 422
    assert client.post("/api/auth/login", json={"username": "emma' OR 1=1--", "password": "x"}).status_code == 422
    assert client.post("/api/me/decisions/not-a-uuid/cta", headers=emma, json={"cta_id": "start_review"}).status_code == 422
    assert client.put("/api/me/consents/unknownfam", headers=emma, json={"enabled": False}).status_code == 404
    assert client.put("/api/me/consents/digital", headers=emma, json={"enabled": False, "customer_id": "c_002"}).status_code == 422


def test_body_size_limit(client):
    r = client.post("/api/auth/login", content=b"{" + b" " * 20000 + b"}", headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_security_headers(client):
    r = client.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_advisor_journal_requires_assigned_task(client):
    emma = login(client, "emma")
    did = client.get("/api/me/feed", headers=emma).json()["decision_id"]
    adv = login(client, "conseiller")
    assert client.get(f"/api/advisor/decisions/{did}", headers=adv).status_code == 404   # aucune tâche pour Emma
    client.post(f"/api/me/decisions/{did}/cta", headers=emma, json={"cta_id": "book_appointment"})
    assert client.get(f"/api/advisor/decisions/{did}", headers=adv).status_code == 200
