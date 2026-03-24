"""X-API-Key authentication for the Integration API.

Portfolio companies authenticate by including their API key in the
X-API-Key header. Keys are stored as SHA-256 hashes in the
organizations table.
"""
import hashlib
import secrets
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db
from core.models import Organization


KEY_PREFIX = "laith_"


def generate_api_key() -> str:
    """Generate a new API key with laith_ prefix."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    """Hash an API key for storage. Uses SHA-256 (fast, sufficient for API keys)."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_current_org(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Organization:
    """FastAPI dependency: validate X-API-Key header and return the Organization.

    Raises 401 if key is invalid or no database is configured.
    """
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Integration API requires DATABASE_URL.",
        )

    key_hash = hash_api_key(x_api_key)
    org = db.query(Organization).filter_by(api_key_hash=key_hash).first()

    if org is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    return org
