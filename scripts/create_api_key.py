"""Generate an API key for a portfolio company organization.

Usage:
    python scripts/create_api_key.py <org_name>

Example:
    python scripts/create_api_key.py klaim
    > API key for klaim: laith_abc123...
    > Key hash stored in organizations table.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, SessionLocal
from core.models import Organization
from backend.auth import generate_api_key, hash_api_key


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_api_key.py <org_name>")
        print("Example: python scripts/create_api_key.py klaim")
        sys.exit(1)

    org_name = sys.argv[1]

    if engine is None:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(name=org_name).first()
        if not org:
            print(f"ERROR: Organization '{org_name}' not found in database.")
            print(f"Available: {[o.name for o in db.query(Organization).all()]}")
            sys.exit(1)

        key = generate_api_key()
        org.api_key_hash = hash_api_key(key)
        db.commit()

        print(f"\nAPI key for {org_name}: {key}")
        print(f"Key hash stored in organizations table.")
        print(f"\nUse this header in API requests:")
        print(f'  X-API-Key: {key}')
        print(f"\nTest with:")
        print(f'  curl -H "X-API-Key: {key}" http://localhost:8000/api/integration/invoices')
    finally:
        db.close()


if __name__ == '__main__':
    main()
