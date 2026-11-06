"""ORION Authentication, Session Verification, and Dependency Injection."""

import secrets
from datetime import UTC, datetime

import jwt
from fastapi import Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    AccessRestrictedError,
    AccountDisabledError,
    AuthenticationRequiredError,
    CSRFValidationError,
    UnauthorizedAccessError,
)
from app.core.logging import logger
from app.db.session import get_db
from app.models.user import User, UserSession
from app.security.service import decode_session_jwt


class AuthenticatedUser(BaseModel):
    id: str
    email: str = "researcher@orion-assistant.ai"
    role: str = "researcher"
    access_status: str = "pending_request"
    display_name: str | None = None

    @property
    def is_admin(self) -> bool:
        if self.role in ("admin", "administrator"):
            return True
        admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
        if self.email and self.email.strip().lower() in admin_emails:
            return True
        admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
        if self.id and self.id.strip() in admin_ids:
            return True
        return False

    @property
    def is_active_researcher(self) -> bool:
        return self.is_admin or self.access_status == "active"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None),
) -> AuthenticatedUser:
    """Extract and securely verify the authenticated user from cookie session, Bearer JWT, or dev bypass."""
    session_token: str | None = None
    is_cookie_auth = False

    # 1. Prefer Authorization: Bearer <token> (explicit header authentication is immune to ambient cookie CSRF)
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.split(" ", 1)[1].strip()
        is_cookie_auth = False

    # 2. HttpOnly Cookie session (ambient browser credential requiring CSRF validation)
    elif request.cookies.get(settings.SESSION_COOKIE_NAME):
        session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
        is_cookie_auth = True

    # 3. If a session token exists, perform cryptographic and DB verification
    if session_token:
        # Enforce CSRF protection for cookie-authenticated mutation requests
        if is_cookie_auth and request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            csrf_header = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")
            csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)

            if csrf_header:
                csrf_header = csrf_header.strip().strip('"')
            if csrf_cookie:
                csrf_cookie = csrf_cookie.strip().strip('"')

            if (
                not csrf_header
                or not csrf_cookie
                or not secrets.compare_digest(csrf_header, csrf_cookie)
            ):
                logger.warning("CSRF validation mismatch on state-changing request.")
                raise CSRFValidationError()

        try:
            payload = decode_session_jwt(session_token)
            user_id = payload.get("sub")
            session_id = payload.get("jti")

            if not user_id or not session_id:
                raise AuthenticationRequiredError("Malformed authentication token.")

            # Verify session in database (enforce logout/revocation and expiry)
            session_stmt = select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
            )
            sess_res = await db.execute(session_stmt)
            user_session = sess_res.scalar_one_or_none()

            if not user_session:
                raise AuthenticationRequiredError("Session does not exist or has been revoked.")

            if user_session.is_revoked:
                raise AuthenticationRequiredError("Session has been revoked.")

            now_utc = datetime.now(UTC)
            # Ensure timezone-aware comparison
            session_expires = user_session.expires_at
            if session_expires.tzinfo is None:
                session_expires = session_expires.replace(tzinfo=UTC)

            if session_expires < now_utc:
                raise AuthenticationRequiredError("Session has expired.")

            # Verify user account in database
            user_stmt = select(User).where(User.id == user_id)
            user_res = await db.execute(user_stmt)
            db_user = user_res.scalar_one_or_none()

            if not db_user:
                raise AuthenticationRequiredError("User account not found.")

            if not db_user.is_active or db_user.status != "active":
                raise AccountDisabledError()

            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
            admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
            is_admin_user = (
                getattr(db_user, "role", None) == "admin"
                or (db_user.email and db_user.email.strip().lower() in admin_emails)
                or (db_user.id and db_user.id.strip() in admin_ids)
            )
            user_role = "admin" if is_admin_user else (getattr(db_user, "role", None) or "researcher")
            user_access_status = "active" if is_admin_user else (getattr(db_user, "access_status", None) or "pending_request")

            return AuthenticatedUser(
                id=db_user.id,
                email=db_user.email,
                role=user_role,
                access_status=user_access_status,
                display_name=db_user.display_name,
            )

        except jwt.ExpiredSignatureError:
            raise AuthenticationRequiredError("Authentication session has expired.")
        except jwt.InvalidTokenError as e:
            # Optional Supabase legacy token fallback if configured
            if settings.SUPABASE_JWT_SECRET:
                try:
                    sp_payload = jwt.decode(
                        session_token,
                        settings.SUPABASE_JWT_SECRET,
                        algorithms=["HS256"],
                        audience="authenticated",
                    )
                    sp_user_id = sp_payload.get("sub")
                    if sp_user_id:
                        sp_email = sp_payload.get("email", f"{sp_user_id}@orion-user.ai")
                        return AuthenticatedUser(id=sp_user_id, email=sp_email)
                except Exception:
                    pass
            logger.warning(f"Invalid authentication token: {e}")
            raise AuthenticationRequiredError("Invalid authentication credentials.")

    # 4. Fallback for isolated offline dev/test environments only
    if settings.DEV_AUTH_BYPASS and settings.ORION_ENV == "development":
        user_id = x_user_id or "user_dev_researcher_001"
        admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
        admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
        is_admin_user = (
            user_id.strip() in admin_ids
            or f"{user_id.strip()}@orion.dev".lower() in admin_emails
        )
        user_role = "admin" if is_admin_user else "researcher"
        return AuthenticatedUser(
            id=user_id,
            email=f"{user_id}@orion.dev",
            role=user_role,
            access_status="active",
        )

    # 5. Strictly unauthenticated
    if x_user_id:
        logger.warning(
            f"Blocked unauthenticated X-User-Id header spoofing attempt for user '{x_user_id}'. "
            "DEV_AUTH_BYPASS is disabled."
        )
    raise AuthenticationRequiredError("Authentication credentials were not provided or are invalid.")


async def require_active_researcher(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Ensure that the authenticated user possesses an active research workspace.

    Admins are always granted full access to research capabilities without restriction.
    Researchers must possess access_status == 'active'.
    Pending or revoked users receive an explicit HTTP 403 with machine-readable error code.
    """
    if current_user.is_admin:
        return current_user

    status = current_user.access_status
    if status == "active":
        return current_user

    if status in ("pending_request", "request_submitted"):
        raise AccessRestrictedError(
            "access_pending",
            "Your research access is pending administrator review.",
        )
    elif status == "approved_invitation_pending":
        raise AccessRestrictedError(
            "invitation_pending",
            "Your access has been approved; invitation redemption is required to activate your workspace.",
        )
    elif status == "rejected":
        raise AccessRestrictedError(
            "access_rejected",
            "Your research access request has been declined.",
        )
    elif status == "revoked":
        raise AccessRestrictedError(
            "access_revoked",
            "Your research access has been revoked.",
        )
    else:
        raise AccessRestrictedError(
            "access_restricted",
            f"Research access is restricted for account status '{status}'.",
        )


async def require_admin_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Ensure that the authenticated user possesses administrative privileges."""
    if not current_user.is_admin:
        raise UnauthorizedAccessError(
            "Administrative privileges are required to access this endpoint."
        )
    return current_user
