"""ORION Authentication and JWT verification."""


import jwt
from fastapi import Header
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AuthenticationRequiredError
from app.core.logging import logger


class AuthenticatedUser(BaseModel):
    id: str
    email: str = "researcher@orion-assistant.ai"
    role: str = "authenticated"


async def get_current_user(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None),
) -> AuthenticatedUser:
    """Extract and verify the authenticated user from the Bearer token or dev session."""
    # Development Bypass (Strictly forbidden in production by config validator)
    if settings.DEV_AUTH_BYPASS and settings.ORION_ENV != "production":
        user_id = x_user_id or "user_dev_researcher_001"
        return AuthenticatedUser(id=user_id, email=f"{user_id}@orion.dev")

    # Production JWT Verification (Supabase Auth)
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationRequiredError("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()

    if not settings.SUPABASE_JWT_SECRET:
        logger.error("SUPABASE_JWT_SECRET is not configured in production.")
        raise AuthenticationRequiredError("Server authentication configuration error.")

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationRequiredError("Token does not contain a subject (sub) claim.")

        email = payload.get("email", f"{user_id}@orion-user.ai")
        return AuthenticatedUser(id=user_id, email=email)

    except jwt.ExpiredSignatureError:
        raise AuthenticationRequiredError("Authentication token has expired.")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid authentication token: {e}")
        raise AuthenticationRequiredError("Invalid authentication credentials.")
