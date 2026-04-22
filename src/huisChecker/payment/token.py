"""Signed, time-limited access tokens for paid reports."""

from __future__ import annotations

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SALT = "report-access"
_ONE_YEAR = 365 * 24 * 3600


def _serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    return URLSafeTimedSerializer(secret)


def generate_token(address_id: str) -> str:
    return _serializer().dumps(address_id, salt=_SALT)


def validate_token(token: str, max_age: int = _ONE_YEAR) -> str | None:
    """Return the address_id if the token is valid and unexpired, else None."""
    try:
        return _serializer().loads(token, salt=_SALT, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
