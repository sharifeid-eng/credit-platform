"""Auth API routes — user profile and admin user management.

Authentication is handled by Cloudflare Access. These endpoints read the
verified user identity and manage role assignments.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from backend.cf_auth import get_current_user, require_admin, CF_TEAM

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: str
    name: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _user_out(u: User) -> dict:
    return {
        "id": str(u.id) if u.id else "dev",
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "is_active": u.is_active if u.is_active is not None else True,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


# ── Current user ─────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return _user_out(user)


# ── Logout helper ────────────────────────────────────────────────────────────

@router.get("/logout-url")
def get_logout_url():
    """Return the Cloudflare Access logout URL."""
    if CF_TEAM:
        return {"url": f"https://{CF_TEAM}.cloudflareaccess.com/cdn-cgi/access/logout"}
    return {"url": "/"}


# ── Admin: user management ───────────────────────────────────────────────────

@router.get("/users")
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all platform users (admin only)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database required")
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_out(u) for u in users]


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Pre-provision a user with a role (admin only).

    The user will be auto-matched when they first authenticate via Cloudflare.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database required")

    if body.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'viewer'")

    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        email=body.email.lower(),
        name=body.name,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a user's name, role, or active status (admin only)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database required")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-demotion/deactivation
    if admin.id and str(admin.id) == user_id:
        if body.role and body.role != "admin":
            raise HTTPException(status_code=400, detail="Cannot demote yourself")
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        if body.role not in ("admin", "viewer"):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'viewer'")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a user (admin only). Sets is_active=False."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database required")

    if admin.id and str(admin.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    return {"message": f"User {user.email} deactivated"}
