"""ORION Authentication API Endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedUser, get_current_user, get_db
from app.core.config import settings
from app.core.errors import (
    AccountDisabledError,
    AuthenticationRequiredError,
    DuplicateEmailError,
    InvalidCredentialsError,
    RateLimitExceededError,
)
from app.db.base import generate_uuid
from app.models.access_control import AccessRequest, Invitation
from app.models.auth_event import AuthAuditEvent
from app.models.user import User, UserSession
from app.schemas.access_control import (
    AccessRequestCreate,
    AccessRequestResponse,
    RedeemInvitationRequest,
)
from app.schemas.user import (
    AuthSessionResponse,
    ChangePasswordRequest,
    MessageResponse,
    SessionItemResponse,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security.service import (
    auth_rate_limiter,
    create_session_jwt,
    decode_session_jwt,
    generate_csrf_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.security.state_machine import AccessStatus, transition_access_status

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str:
    """Extract client IP address accounting for proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def _resolve_user_role(user_id: str, email: str | None, current_role: str | None = None) -> str:
    """Determine whether the user is an administrator based on configured criteria."""
    if current_role == "admin":
        return "admin"
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    if email and email.strip().lower() in admin_emails:
        return "admin"
    admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
    if user_id and user_id.strip() in admin_ids:
        return "admin"
    return current_role or "researcher"


def _build_user_response(user: User) -> UserResponse:
    """Construct UserResponse with dynamic role and access status resolution."""
    role = _resolve_user_role(user.id, user.email, getattr(user, "role", None))
    access_status = "active" if role == "admin" else (getattr(user, "access_status", "pending_request") or "pending_request")
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=role,
        access_status=access_status,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new researcher account",
)
async def register(
    payload: UserRegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Register a new user account with Argon2id password hashing and issue a secure session."""
    client_ip = _get_client_ip(request)

    # 1. Rate limiting
    if not auth_rate_limiter.check_rate_limit(
        f"register:{client_ip}",
        max_attempts=settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS,
        window_seconds=settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS,
    ):
        raise RateLimitExceededError("Too many registration attempts. Please try again later.")

    # 2. Check for duplicate account
    existing_user_stmt = select(User).where(User.email == payload.email)
    res = await db.execute(existing_user_stmt)
    if res.scalar_one_or_none():
        raise DuplicateEmailError("An account with this email address already exists.")

    # 3. Create user with Argon2id password hash
    hashed = hash_password(payload.password)
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    is_admin_email = payload.email.strip().lower() in admin_emails
    assigned_role = "admin" if is_admin_email else "researcher"
    assigned_access_status = "active" if is_admin_email else "pending_request"

    user = User(
        email=payload.email,
        hashed_password=hashed,
        display_name=payload.display_name,
        institution=payload.institution,
        status="active",
        is_active=True,
        role=assigned_role,
        access_status=assigned_access_status,
    )
    db.add(user)
    await db.flush()

    # 4. Create persistent session record and record registration audit event
    session_id = generate_uuid("sess")
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    session = UserSession(
        id=session_id,
        user_id=user.id,
        session_token_hash=hash_token(session_id),
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", "")[:255],
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(session)

    audit_evt = AuthAuditEvent(
        id=generate_uuid("evt"),
        user_id=user.id,
        email=user.email,
        event_type="register",
        success=True,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    db.add(audit_evt)
    await db.commit()
    await db.refresh(user)

    # 5. Issue JWT and CSRF tokens
    token = create_session_jwt(user.id, user.email, session_id)
    csrf_token = generate_csrf_token()

    # 6. Set HttpOnly session cookie and readable CSRF cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=False,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )

    return AuthSessionResponse(
        user=_build_user_response(user),
        access_token=token,
        token_type="bearer",
        expires_in=settings.SESSION_EXPIRE_MINUTES * 60,
        csrf_token=csrf_token,
    )


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
)
async def login(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Authenticate credentials, establish a session, and set secure cookies."""
    client_ip = _get_client_ip(request)
    rate_key = f"login:{client_ip}:{payload.email}"

    # 1. Rate limiting
    if not auth_rate_limiter.check_rate_limit(
        rate_key,
        max_attempts=settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    ):
        try:
            audit_evt = AuthAuditEvent(
                id=generate_uuid("evt"),
                email=payload.email,
                event_type="login_failure",
                success=False,
                failure_reason="RATE_LIMIT_EXCEEDED",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.add(audit_evt)
            await db.commit()
        except Exception:
            await db.rollback()
        raise RateLimitExceededError("Too many login attempts. Please try again later.")

    # 2. Look up user by email
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        try:
            audit_evt = AuthAuditEvent(
                id=generate_uuid("evt"),
                user_id=user.id if user else None,
                email=payload.email,
                event_type="login_failure",
                success=False,
                failure_reason="INVALID_CREDENTIALS",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.add(audit_evt)
            await db.commit()
        except Exception:
            await db.rollback()
        raise InvalidCredentialsError("Invalid email or password.")

    # 3. Check account active status
    if not user.is_active or user.status != "active":
        try:
            audit_evt = AuthAuditEvent(
                id=generate_uuid("evt"),
                user_id=user.id,
                email=payload.email,
                event_type="login_failure",
                success=False,
                failure_reason="ACCOUNT_DISABLED",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.add(audit_evt)
            await db.commit()
        except Exception:
            await db.rollback()
        raise AccountDisabledError("This account has been deactivated.")

    # 4. Successful login: reset rate limit attempts for this client/email
    auth_rate_limiter.reset(rate_key)

    # 5. Create new session and record login success audit event
    session_id = generate_uuid("sess")
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    session = UserSession(
        id=session_id,
        user_id=user.id,
        session_token_hash=hash_token(session_id),
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", "")[:255],
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(session)

    audit_evt = AuthAuditEvent(
        id=generate_uuid("evt"),
        user_id=user.id,
        email=user.email,
        event_type="login_success",
        success=True,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    db.add(audit_evt)
    await db.commit()
    await db.refresh(user)

    # 6. Issue JWT and CSRF tokens
    token = create_session_jwt(user.id, user.email, session_id)
    csrf_token = generate_csrf_token()

    # 7. Set cookies
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=False,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )

    return AuthSessionResponse(
        user=_build_user_response(user),
        access_token=token,
        token_type="bearer",
        expires_in=settings.SESSION_EXPIRE_MINUTES * 60,
        csrf_token=csrf_token,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    request: Request,
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Retrieve the full profile for the currently authenticated user."""
    # Ensure active session always has a synchronized CSRF cookie & response header
    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not csrf_cookie:
        csrf_cookie = generate_csrf_token()
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_cookie,
            max_age=settings.SESSION_EXPIRE_MINUTES * 60,
            httponly=False,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",
        )
    response.headers["X-CSRF-Token"] = csrf_cookie

    stmt = select(User).where(User.id == current_user.id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        # Development fallback object conversion if user was created via bypass
        role = _resolve_user_role(current_user.id, current_user.email, current_user.role)
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name or current_user.email.split("@")[0],
            institution=None,
            status="active",
            is_active=True,
            role=role,
            access_status="active" if role == "admin" else current_user.access_status,
            created_at=datetime.now(UTC),
        )
    return _build_user_response(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out and invalidate current session",
)
async def logout(
    request: Request,
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke session in database, record audit event, and clear authentication cookies."""
    # Attempt to extract session token from cookie or Authorization header
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if token:
        try:
            payload = decode_session_jwt(token)
            session_id = payload.get("jti")
            if session_id:
                # Invalidate session in database
                stmt = (
                    update(UserSession)
                    .where(UserSession.id == session_id, UserSession.user_id == current_user.id)
                    .values(is_revoked=True)
                )
                await db.execute(stmt)
        except Exception:
            pass

    # Record logout audit event
    try:
        audit_evt = AuthAuditEvent(
            id=generate_uuid("evt"),
            user_id=current_user.id,
            email=current_user.email,
            event_type="logout",
            success=True,
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:255],
        )
        db.add(audit_evt)
        await db.commit()
    except Exception:
        await db.rollback()

    # Clear cookies regardless of token validity
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/")

    return MessageResponse(message="Logged out successfully.")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password for current authenticated user",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify current password, hash new password with Argon2id, and update account."""
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if not user:
        raise AuthenticationRequiredError("Authentication required.")

    if not verify_password(payload.current_password, user.hashed_password):
        raise InvalidCredentialsError("Current password does not match.")

    user.hashed_password = hash_password(payload.new_password)
    audit_evt = AuthAuditEvent(
        id=generate_uuid("evt"),
        user_id=user.id,
        email=user.email,
        event_type="password_change",
        success=True,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    db.add(audit_evt)
    await db.commit()
    return MessageResponse(message="Password changed successfully.")


@router.patch(
    "/profile",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current authenticated user profile",
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update editable profile fields (display name, institution)."""
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if not user:
        raise AuthenticationRequiredError("Authentication required.")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.institution is not None:
        user.institution = payload.institution

    await db.commit()
    await db.refresh(user)
    return _build_user_response(user)


@router.get(
    "/sessions",
    response_model=list[SessionItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List active login sessions for current user",
)
async def list_sessions(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionItemResponse]:
    """Retrieve active and recent login sessions for the authenticated researcher."""
    current_session_id = None
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if token:
        try:
            payload = decode_session_jwt(token)
            current_session_id = payload.get("jti")
        except Exception:
            pass

    now = datetime.now(UTC)
    stmt = (
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .order_by(UserSession.created_at.desc())
        .limit(20)
    )
    sessions = (await db.execute(stmt)).scalars().all()

    items: list[SessionItemResponse] = []
    for s in sessions:
        is_active = (not s.is_revoked) and (s.expires_at > now)
        items.append(
            SessionItemResponse(
                id=s.id,
                ip_address=s.ip_address,
                user_agent=s.user_agent,
                created_at=s.created_at,
                expires_at=s.expires_at,
                is_active=is_active,
                is_current=(s.id == current_session_id),
            )
        )
    return items


@router.post(
    "/sessions/revoke-others",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all other active sessions for current user",
)
async def revoke_other_sessions(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke all sessions belonging to current user except the currently active session."""
    current_session_id = None
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if token:
        try:
            payload = decode_session_jwt(token)
            current_session_id = payload.get("jti")
        except Exception:
            pass

    stmt = update(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.is_revoked == False,
    )
    if current_session_id:
        stmt = stmt.where(UserSession.id != current_session_id)

    stmt = stmt.values(is_revoked=True)
    await db.execute(stmt)
    await db.commit()

    return MessageResponse(message="All other sessions revoked successfully.")


@router.post(
    "/access-request",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or resubmit a research access request",
)
async def submit_access_request(
    payload: AccessRequestCreate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse:
    """Submit a research access request for administrator review."""
    client_ip = _get_client_ip(request)
    user_stmt = select(User).where(User.id == current_user.id)
    user_res = await db.execute(user_stmt)
    db_user = user_res.scalar_one_or_none()
    if not db_user:
        raise AuthenticationRequiredError("User account not found.")

    if db_user.role == "admin" or db_user.access_status == AccessStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account already has active research access.",
        )

    # Check for existing pending request
    pending_stmt = select(AccessRequest).where(
        AccessRequest.user_id == current_user.id,
        AccessRequest.status == "pending",
    )
    pending_res = await db.execute(pending_stmt)
    if pending_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A research access request is already pending review.",
        )

    # Transition state to request_submitted
    await transition_access_status(
        session=db,
        target_user=db_user,
        new_status=AccessStatus.REQUEST_SUBMITTED,
        actor_id=current_user.id,
        actor_role=current_user.role,
        reason="Research access request submitted",
        metadata={"institution": payload.institution, "research_purpose": payload.research_purpose},
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    req_id = generate_uuid("req")
    req = AccessRequest(
        id=req_id,
        user_id=current_user.id,
        institution=payload.institution,
        research_purpose=payload.research_purpose,
        intended_data_types=payload.intended_data_types,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    return AccessRequestResponse(
        id=req.id,
        user_id=req.user_id,
        user_email=db_user.email,
        user_display_name=db_user.display_name,
        institution=req.institution,
        research_purpose=req.research_purpose,
        intended_data_types=req.intended_data_types,
        status=req.status,
        reviewed_by=req.reviewed_by,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.get(
    "/access-request",
    response_model=AccessRequestResponse | None,
    summary="View status of own access request",
)
async def get_own_access_request(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse | None:
    """Retrieve status of the authenticated user's most recent research access request."""
    stmt = (
        select(AccessRequest)
        .where(AccessRequest.user_id == current_user.id)
        .order_by(AccessRequest.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        return None

    return AccessRequestResponse(
        id=req.id,
        user_id=req.user_id,
        user_email=current_user.email,
        user_display_name=current_user.display_name,
        institution=req.institution,
        research_purpose=req.research_purpose,
        intended_data_types=req.intended_data_types,
        status=req.status,
        reviewed_by=req.reviewed_by,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.post(
    "/invitations/redeem",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Redeem cryptographic invitation token to activate researcher workspace",
)
async def redeem_invitation(
    payload: RedeemInvitationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Validate and redeem a one-time cryptographic invitation token."""
    client_ip = _get_client_ip(request)
    token_h = hash_token(payload.invitation_token.strip())

    # 1. Exclusive row-level lock on PostgreSQL, or standard select
    stmt = select(Invitation).where(Invitation.token_hash == token_h)
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or unrecognized invitation token.",
        )

    if invitation.is_redeemed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation token has already been redeemed.",
        )

    now_utc = datetime.now(UTC)
    inv_expires = invitation.expires_at
    if inv_expires.tzinfo is None:
        inv_expires = inv_expires.replace(tzinfo=UTC)

    if inv_expires < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation token has expired.",
        )

    # 2. Atomic Compare-and-Swap claim: guarantees single-use under high concurrency
    claim_stmt = (
        update(Invitation)
        .where(
            Invitation.id == invitation.id,
            Invitation.is_redeemed.is_(False),
        )
        .values(
            is_redeemed=True,
            redeemed_at=now_utc,
        )
    )
    claim_res = await db.execute(claim_stmt)
    if claim_res.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation token has already been redeemed.",
        )

    # 3. Fetch user
    user_stmt = select(User).where(User.id == invitation.user_id)
    u_res = await db.execute(user_stmt)
    target_user = u_res.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated user account not found.",
        )

    # 4. Execute transition to active
    await transition_access_status(
        session=db,
        target_user=target_user,
        new_status=AccessStatus.ACTIVE,
        actor_id=target_user.id,
        actor_role="user",
        reason="Cryptographic invitation redeemed",
        metadata={"invitation_id": invitation.id},
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    await db.commit()

    return MessageResponse(message="Invitation successfully redeemed. Research workspace activated.")


