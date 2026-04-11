"""Cloudflare Access JWT verification + role-based access for Laith.

Reads the CF_Authorization cookie or Cf-Access-Jwt-Assertion header set by
Cloudflare Access, verifies the JWT against Cloudflare's public keys, and
maps the authenticated email to a User record with a role (admin/viewer).

When CF_TEAM is not set (local dev), auth is skipped entirely.
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import Optional

import jwt
import httpx
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.database import get_db, SessionLocal
from core.models import User

logger = logging.getLogger("laith.auth")

# ── Configuration ────────────────────────────────────────────────────────────

_raw_cf_team = os.getenv("CF_TEAM")
CF_TEAM = _raw_cf_team.strip() if _raw_cf_team and _raw_cf_team.strip() else None
if _raw_cf_team is not None and CF_TEAM is None:
    logger.warning("CF_TEAM is set but empty/whitespace — treating as not configured (dev mode)")
CF_APP_AUD = os.getenv("CF_APP_AUD")  # Application audience tag from CF dashboard
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")  # Bootstrap first admin

CERTS_URL = f"https://{CF_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs" if CF_TEAM else None
ISSUER = f"https://{CF_TEAM}.cloudflareaccess.com" if CF_TEAM else None

# ── Public key cache ─────────────────────────────────────────────────────────

_keys_cache = {"keys": [], "fetched_at": 0}
KEYS_TTL = 3600  # Refresh keys every hour


def _get_public_keys():
    """Fetch and cache Cloudflare Access public keys (JWKS)."""
    now = time.time()
    if _keys_cache["keys"] and (now - _keys_cache["fetched_at"]) < KEYS_TTL:
        return _keys_cache["keys"]

    try:
        resp = httpx.get(CERTS_URL, timeout=10)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        _keys_cache["keys"] = keys
        _keys_cache["fetched_at"] = now
        return keys
    except Exception as e:
        logger.error(f"Failed to fetch CF public keys: {e}")
        if _keys_cache["keys"]:
            return _keys_cache["keys"]  # Use stale cache
        raise HTTPException(status_code=503, detail="Cannot verify authentication")


def _verify_cf_token(token: str) -> dict:
    """Verify a Cloudflare Access JWT and return its claims."""
    keys = _get_public_keys()

    # Decode header to find key ID
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    kid = unverified_header.get("kid")
    key_data = next((k for k in keys if k.get("kid") == kid), None)

    if not key_data:
        # Key rotation — force refresh and retry
        _keys_cache["fetched_at"] = 0
        keys = _get_public_keys()
        key_data = next((k for k in keys if k.get("kid") == kid), None)
        if not key_data:
            raise HTTPException(status_code=401, detail="Token signing key not found")

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=CF_APP_AUD,
            issuer=ISSUER,
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid audience")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── Token extraction ─────────────────────────────────────────────────────────

def _extract_cf_token(request: Request) -> Optional[str]:
    """Extract CF token from cookie or header."""
    token = request.cookies.get("CF_Authorization")
    if not token:
        token = request.headers.get("Cf-Access-Jwt-Assertion")
    return token


# ── User lookup / auto-provision ─────────────────────────────────────────────

def _get_or_create_user(db: Session, email: str) -> User:
    """Find existing user or auto-provision as viewer."""
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.last_login_at = datetime.utcnow()
        db.commit()
        return user

    # Auto-provision: first user with ADMIN_EMAIL gets admin, others get viewer
    role = "admin" if (ADMIN_EMAIL and email.lower() == ADMIN_EMAIL.lower()) else "viewer"
    name = email.split("@")[0].replace(".", " ").title()

    user = User(
        email=email.lower(),
        name=name,
        role=role,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"Auto-provisioned user: {email} as {role}")
    return user


# ── FastAPI dependencies ─────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: returns the authenticated User."""
    if not CF_TEAM:
        # Dev mode — return a mock admin user
        return User(
            email="dev@localhost",
            name="Dev User",
            role="admin",
            is_active=True,
        )

    if db is None:
        raise HTTPException(status_code=503, detail="Database required for authentication")

    token = _extract_cf_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    claims = _verify_cf_token(token)
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="No email in token")

    user = _get_or_create_user(db, email)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: requires admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Middleware ────────────────────────────────────────────────────────────────

# Paths that skip user auth (they have their own auth or are public)
_SKIP_PREFIXES = (
    "/auth/",
    "/api/integration/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class CloudflareAuthMiddleware(BaseHTTPMiddleware):
    """Verify Cloudflare Access JWT on all requests (except skipped paths).

    When CF_TEAM is not set, passes all requests through (dev mode).
    """

    async def dispatch(self, request: Request, call_next):
        # Dev mode — no auth
        if not CF_TEAM:
            return await call_next(request)

        # Skip paths that handle their own auth
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Verify CF token
        token = _extract_cf_token(request)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

        try:
            claims = _verify_cf_token(token)
            request.state.cf_email = claims.get("email", "")
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

        return await call_next(request)


# ── Bootstrap ────────────────────────────────────────────────────────────────

def bootstrap_admin():
    """Create the first admin user if the users table is empty."""
    if not ADMIN_EMAIL or not SessionLocal:
        return

    db = SessionLocal()
    try:
        count = db.query(User).count()
        if count == 0:
            user = User(
                email=ADMIN_EMAIL.lower(),
                name=ADMIN_EMAIL.split("@")[0].replace(".", " ").title(),
                role="admin",
            )
            db.add(user)
            db.commit()
            logger.info(f"Bootstrapped admin user: {ADMIN_EMAIL}")
        else:
            logger.info(f"Users table has {count} users, skipping bootstrap.")
    except Exception as e:
        logger.warning(f"Bootstrap skipped (table may not exist yet): {e}")
        db.rollback()
    finally:
        db.close()
