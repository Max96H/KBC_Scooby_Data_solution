"""Authentification, autorisation et protections transverses.

- Mots de passe : PBKDF2-HMAC-SHA256, 200 000 itérations, sel aléatoire, comparaison à temps constant.
- Session : JWT HS256 signé avec SECRET_KEY (environnement), durée courte, envoyé en en-tête Authorization
  (pas de cookie -> pas de CSRF).
- L'identité du client vient TOUJOURS du token, jamais d'un paramètre d'URL ou du corps de la requête.
- Limitation des tentatives de connexion par IP et par identifiant.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.db import get_conn

PBKDF2_ITERATIONS = 200_000
_bearer = HTTPBearer(auto_error=False)
# Hash factice pour que la vérification dure le même temps quand l'utilisateur n'existe pas
_DUMMY_HASH: str | None = None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    verify_password(password, _DUMMY_HASH)


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    customer_id: str | None


def create_token(user: Principal) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "cid": user.customer_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise", headers={"WWW-Authenticate": "Bearer"})


def current_principal(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"],
                             options={"require": ["exp", "sub", "role"]})
    except jwt.PyJWTError:
        raise _unauthorized()
    # Le compte doit toujours exister et garder le même rôle (révocation possible en supprimant l'utilisateur)
    with get_conn() as conn:
        row = conn.execute("SELECT username, role, customer_id FROM users WHERE username = ?", (payload["sub"],)).fetchone()
    if row is None or row["role"] != payload["role"] or row["customer_id"] != payload.get("cid"):
        raise _unauthorized()
    return Principal(row["username"], row["role"], row["customer_id"])


def require_customer(p: Principal = Depends(current_principal)) -> Principal:
    if p.role != "customer" or not p.customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux clients")
    return p


def require_advisor(p: Principal = Depends(current_principal)) -> Principal:
    if p.role != "advisor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux conseillers")
    return p


class LoginRateLimiter:
    """Fenêtre glissante en mémoire (suffisant pour un PoC mono-instance ; Redis en production)."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                q = self._hits[key]
                while q and now - q[0] > self.window:
                    q.popleft()
                if len(q) >= self.max_attempts:
                    raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives, réessayez plus tard")

    def fail(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._hits[key].append(now)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._hits.pop(key, None)


login_limiter = LoginRateLimiter(settings.login_max_attempts, settings.login_window_seconds)


def client_ip(request: Request) -> str:
    # On ne fait PAS confiance à X-Forwarded-For (falsifiable) sans reverse proxy configuré
    return request.client.host if request.client else "unknown"
