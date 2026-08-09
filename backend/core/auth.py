"""Authentication utilities for admin endpoints."""

import hmac

from fastapi import HTTPException, status
from core.config import ADMIN_TOKEN


def verify_admin_token(token: str) -> bool:
    """Verify that the provided token matches the admin token."""
    if not ADMIN_TOKEN:
        return False
    # Constant-time comparison so response timing does not leak the token.
    return hmac.compare_digest(token, ADMIN_TOKEN)


def check_admin_auth(authorization_header: str = None) -> bool:
    """Check if the request has valid admin authentication."""
    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format",
        )

    token = parts[1]
    if not verify_admin_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return True
