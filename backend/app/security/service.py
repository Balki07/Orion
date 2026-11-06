"""Security and Authentication cryptographic service."""

import hashlib
import re
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# OWASP Recommended Argon2id parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Email validation regex conforming to RFC 5322 simplified
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> None:
    """Validate password strength against NIST / OWASP guidelines."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_~`\-+=\[\]\\;\'/]', password):
        raise ValueError("Password must contain at least one special character.")


def normalize_email(email: str) -> str:
    """Normalize and validate email address."""
    if not email:
        raise ValueError("Email address cannot be empty.")
    normalized = email.strip().lower()
    if not EMAIL_REGEX.match(normalized):
        raise ValueError("Invalid email address format.")
    return normalized


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random token for CSRF protection."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for database lookup and storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_jwt(
    user_id: str,
    email: str,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT for a user session."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "email": email,
        "jti": session_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "session",
    }
    return jwt.encode(payload, settings.ORION_SECRET_KEY, algorithm="HS256")


def decode_session_jwt(token: str) -> dict[str, Any]:
    """Decode and verify a session JWT."""
    return jwt.decode(
        token,
        settings.ORION_SECRET_KEY,
        algorithms=["HS256"],
        options={"require": ["sub", "exp", "jti"]},
    )


class AuthRateLimiter:
    """Thread-safe in-memory rate limiter using sliding timestamp window."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Return True if request is allowed, False if limit is exceeded."""
        now = time.time()
        with self._lock:
            # Purge expired attempt timestamps
            valid_timestamps = [t for t in self._attempts[key] if now - t < window_seconds]
            if len(valid_timestamps) >= max_attempts:
                self._attempts[key] = valid_timestamps
                return False
            valid_timestamps.append(now)
            self._attempts[key] = valid_timestamps
            return True

    def reset(self, key: str) -> None:
        """Reset rate limit history for a specific key."""
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        """Clear all rate limit history."""
        with self._lock:
            self._attempts.clear()


# Global rate limiter instance
auth_rate_limiter = AuthRateLimiter()

