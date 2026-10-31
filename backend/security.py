import hashlib
import hmac
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from .config import get_settings

admin_header = APIKeyHeader(name='X-Admin-Key', auto_error=False)
booking_header = APIKeyHeader(name='X-Booking-Token', auto_error=False)


async def require_admin(key: Annotated[str | None, Depends(admin_header)]):
    expected = get_settings().admin_api_key.get_secret_value()
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(401, 'A valid X-Admin-Key is required')


def management_token(booking_id: UUID) -> str:
    secret = get_settings().booking_secret.get_secret_value().encode()
    return hmac.new(secret, str(booking_id).encode(), hashlib.sha256).hexdigest()


def authorize_booking(booking_id: UUID, token: str | None):
    if not token or not secrets.compare_digest(token, management_token(booking_id)):
        raise HTTPException(401, 'A valid X-Booking-Token is required')
