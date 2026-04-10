"""
AirVision Helper Utilities
Common helper functions used across the application.
"""

from datetime import datetime, timedelta
import jwt
from app.config import settings


def create_jwt_token(user_id: int, email: str) -> str:
    """
    Create a JWT access token for authenticated users.

    Args:
        user_id: The user's database ID
        email: The user's email address

    Returns:
        Encoded JWT token string
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: Encoded JWT token string

    Returns:
        Decoded payload dictionary

    Raises:
        jwt.ExpiredSignatureError: If the token has expired
        jwt.InvalidTokenError: If the token is invalid
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def format_datetime(dt) -> str:
    """Format a datetime object to ISO 8601 string."""
    if isinstance(dt, str):
        return dt
    if dt:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return ""


def safe_float(value, default=None) -> float:
    """Safely convert a value to float."""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0) -> int:
    """Safely convert a value to int."""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default
