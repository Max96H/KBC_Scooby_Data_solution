from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.db import get_conn
from app.schemas import LoginIn
from app.security import Principal, client_ip, create_token, dummy_verify, login_limiter, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request) -> dict:
    ip_key, user_key = f"ip:{client_ip(request)}", f"user:{body.username}"
    login_limiter.check(ip_key, user_key)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.username, u.password_hash, u.role, u.customer_id, c.display_name, c.first_name, c.language "
            "FROM users u LEFT JOIN customers c ON c.id = u.customer_id WHERE u.username = ?",
            (body.username,),
        ).fetchone()
    if row is None:
        dummy_verify(body.password)        # constant time: does not reveal whether the username exists
        ok = False
    else:
        ok = verify_password(body.password, row["password_hash"])
    if not ok:
        login_limiter.fail(ip_key, user_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    login_limiter.reset(user_key)
    principal = Principal(row["username"], row["role"], row["customer_id"])
    return {
        "token": create_token(principal),
        "token_type": "bearer",
        "expires_in": settings.token_ttl_minutes * 60,
        "role": row["role"],
        "display_name": row["display_name"] or "Advisor",
        "first_name": row["first_name"] or "Advisor",
        "language": row["language"] or "en",
    }
