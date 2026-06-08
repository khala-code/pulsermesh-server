from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str = Security(api_key_header)):
    """
    Node-level auth — used for admin operations (registering stewards,
    validating pulses). Must match the node's API_KEY_SECRET.
    """
    if not api_key or api_key != settings.api_key_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing node API key"
        )
    return api_key


def require_steward_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
):
    """
    Steward-level auth — used for pulse submission and identity reads.
    Validates against the steward's OaZaTa-derived API key.

    v1: lookup by derived key hash.
    v2: this becomes the interference pattern vibe check —
        the key is the steward's rotor phase proof, validated against
        the T3 reference wave at the current checkpoint.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )

    # Node key also passes steward auth (admin override)
    if api_key == settings.api_key_secret:
        return None  # admin context, no specific steward

    from app.services.identity import validate_api_key
    identity = validate_api_key(db, api_key)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid steward key — vibe check failed"
        )
    return identity
