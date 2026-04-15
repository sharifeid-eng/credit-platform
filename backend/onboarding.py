"""
Self-service onboarding API for new portfolio companies.

Allows admin users to create an organization, products, and generate
integration API keys without CLI access.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.post("/validate")
def validate_org_name(body: dict = {}):
    """Check if an organization name is available."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    try:
        from core.database import get_session
        session = get_session()
        if session is None:
            raise HTTPException(status_code=503, detail="Database not configured")

        from core.models import Organization
        existing = session.query(Organization).filter_by(name=name).first()
        session.close()
        return {"available": existing is None, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("validate_org_name failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/organizations")
def create_organization(body: dict = {}):
    """Create a new organization with initial product and API key.

    Body:
        name: Organization name (required)
        admin_email: Admin contact email (required)
        products: List of product dicts, each with:
            - name: Product name (required)
            - currency: Currency code (required, e.g. 'SAR')
            - analysis_type: One of 'klaim', 'silq', 'aajil', or custom (required)
            - description: Product description (optional)

    Returns:
        org_id, api_key (plaintext, shown only once), product_ids
    """
    name = body.get("name", "").strip()
    admin_email = body.get("admin_email", "").strip()
    products = body.get("products", [])

    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not admin_email:
        raise HTTPException(status_code=400, detail="admin_email is required")
    if not products:
        raise HTTPException(status_code=400, detail="At least one product is required")

    try:
        from core.database import get_session
        session = get_session()
        if session is None:
            raise HTTPException(status_code=503, detail="Database not configured. Set DATABASE_URL in .env")

        from core.models import Organization, Product
        from backend.auth import generate_api_key, hash_api_key

        # Check uniqueness
        existing = session.query(Organization).filter_by(name=name).first()
        if existing:
            session.close()
            raise HTTPException(status_code=409, detail=f"Organization '{name}' already exists")

        # Generate API key
        plaintext_key = generate_api_key()
        key_hash = hash_api_key(plaintext_key)

        # Create org
        org = Organization(name=name, api_key_hash=key_hash)
        session.add(org)
        session.flush()  # get org.id

        # Create products
        product_ids = []
        for p in products:
            p_name = p.get("name", "").strip()
            p_currency = p.get("currency", "USD")
            p_analysis_type = p.get("analysis_type", "")
            p_description = p.get("description", "")

            if not p_name:
                continue

            prod = Product(
                organization_id=org.id,
                name=p_name,
                analysis_type=p_analysis_type,
                currency=p_currency,
                description=p_description,
            )
            session.add(prod)
            session.flush()
            product_ids.append({"id": prod.id, "name": p_name})

        session.commit()

        result = {
            "org_id": org.id,
            "org_name": name,
            "api_key": plaintext_key,
            "api_key_warning": "This key is shown only once. Store it securely.",
            "products": product_ids,
            "admin_email": admin_email,
            "next_steps": [
                f"Use the API key with X-API-Key header to push data via /api/integration/ endpoints",
                f"Products created: {', '.join(p['name'] for p in product_ids)}",
            ],
        }

        session.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_organization failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
