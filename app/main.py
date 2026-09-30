"""FastAPI entry point: API + static front end + security headers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT, settings
from app.db import init_db
from app.routes import advisor, auth, customer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Moments - life-moment engine (PoC)",
    version="2.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self' blob:; connect-src 'self'; font-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
MAX_BODY_BYTES = 16 * 1024


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    # Security decisions use the RAW routed path from the ASGI scope, never the reconstructed URL
    # object (it is rebuilt from the Host header, which an attacker controls).
    if request.scope.get("path", "").startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
# Added last = runs first: any request whose Host header is not in the allow-list is rejected (400)
# before it reaches the application. Defence in depth against Host header injection.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    # Never send an internal trace to the client
    logging.getLogger("moments").exception("Unhandled error: %s", type(exc).__name__)
    return JSONResponse({"detail": "Internal error"}, status_code=500)


app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(advisor.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm": bool(settings.gemini_api_key), "voice": bool(settings.elevenlabs_api_key),
            "demo_mode": settings.demo_mode}


STATIC = ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/advisor", include_in_schema=False)
def advisor_page() -> FileResponse:
    return FileResponse(STATIC / "dashboard.html")
