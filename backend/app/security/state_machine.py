"""ORION Research Access Status Enum, State Transitions, and Audit Integration."""

from enum import Enum
from typing import Any, NamedTuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransitionError
from app.core.logging import logger
from app.db.base import generate_uuid
from app.models.auth_event import AuthAuditEvent
from app.models.user import User, UserSession


class AccessStatus(str, Enum):
    """Explicit researcher access statuses."""

    PENDING_REQUEST = "pending_request"
    REQUEST_SUBMITTED = "request_submitted"
    APPROVED_INVITATION_PENDING = "approved_invitation_pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    REVOKED = "revoked"


class PlatformRole(str, Enum):
    """Platform-level authorization role."""

    ADMIN = "admin"
    RESEARCHER = "researcher"


class TransitionRule(NamedTuple):
    from_status: AccessStatus
    to_status: AccessStatus
    allowed_actor_roles: tuple[str, ...]
    event_type: str
    description: str


PERMITTED_TRANSITIONS: dict[tuple[AccessStatus, AccessStatus], TransitionRule] = {
    # 1. User submits research access request
    (AccessStatus.PENDING_REQUEST, AccessStatus.REQUEST_SUBMITTED): TransitionRule(
        AccessStatus.PENDING_REQUEST,
        AccessStatus.REQUEST_SUBMITTED,
        ("user", "admin"),
        "access_request_submitted",
        "User submits research access request with institutional details",
    ),
    # 2. Administrator approves access request and creates invitation
    (AccessStatus.REQUEST_SUBMITTED, AccessStatus.APPROVED_INVITATION_PENDING): TransitionRule(
        AccessStatus.REQUEST_SUBMITTED,
        AccessStatus.APPROVED_INVITATION_PENDING,
        ("admin",),
        "access_request_approved",
        "Administrator approves access request and generates invitation token",
    ),
    # 3. Direct administrator activation without invitation token (e.g. pilot onboarding)
    (AccessStatus.REQUEST_SUBMITTED, AccessStatus.ACTIVE): TransitionRule(
        AccessStatus.REQUEST_SUBMITTED,
        AccessStatus.ACTIVE,
        ("admin",),
        "access_direct_activated",
        "Administrator directly activates researcher workspace without invitation step",
    ),
    (AccessStatus.PENDING_REQUEST, AccessStatus.ACTIVE): TransitionRule(
        AccessStatus.PENDING_REQUEST,
        AccessStatus.ACTIVE,
        ("admin",),
        "admin_direct_activated",
        "Administrator directly activates user account without prior request",
    ),
    # 4. User redeems approved invitation token to activate workspace
    (AccessStatus.APPROVED_INVITATION_PENDING, AccessStatus.ACTIVE): TransitionRule(
        AccessStatus.APPROVED_INVITATION_PENDING,
        AccessStatus.ACTIVE,
        ("user", "admin"),
        "invitation_redeemed",
        "Approved researcher redeems cryptographic invitation token to activate workspace",
    ),
    # 5. Administrator rejects research access request
    (AccessStatus.REQUEST_SUBMITTED, AccessStatus.REJECTED): TransitionRule(
        AccessStatus.REQUEST_SUBMITTED,
        AccessStatus.REJECTED,
        ("admin",),
        "access_request_rejected",
        "Administrator declines researcher access request",
    ),
    # 6. Researcher re-submits after rejection
    (AccessStatus.REJECTED, AccessStatus.REQUEST_SUBMITTED): TransitionRule(
        AccessStatus.REJECTED,
        AccessStatus.REQUEST_SUBMITTED,
        ("user", "admin"),
        "access_request_resubmitted",
        "Researcher submits updated access request following prior rejection",
    ),
    # 7. Administrator revokes active researcher access
    (AccessStatus.ACTIVE, AccessStatus.REVOKED): TransitionRule(
        AccessStatus.ACTIVE,
        AccessStatus.REVOKED,
        ("admin",),
        "access_revoked",
        "Administrator revokes active researcher workspace access",
    ),
    # 8. Administrator cancels approved invitation before redemption
    (AccessStatus.APPROVED_INVITATION_PENDING, AccessStatus.REVOKED): TransitionRule(
        AccessStatus.APPROVED_INVITATION_PENDING,
        AccessStatus.REVOKED,
        ("admin",),
        "invitation_cancelled",
        "Administrator cancels approved researcher invitation",
    ),
    # 9. Administrator reactivates revoked researcher
    (AccessStatus.REVOKED, AccessStatus.ACTIVE): TransitionRule(
        AccessStatus.REVOKED,
        AccessStatus.ACTIVE,
        ("admin",),
        "access_reactivated",
        "Administrator reactivates revoked researcher account",
    ),
    # 10. Revoked researcher requests reconsideration
    (AccessStatus.REVOKED, AccessStatus.REQUEST_SUBMITTED): TransitionRule(
        AccessStatus.REVOKED,
        AccessStatus.REQUEST_SUBMITTED,
        ("user", "admin"),
        "access_reconsideration_requested",
        "Revoked researcher submits formal appeal/reconsideration request",
    ),
}


async def validate_admin_anti_lockout(
    session: AsyncSession,
    target_user: User,
    action: str,  # "revoke" or "demote"
    actor_id: str,
) -> None:
    """Safeguard against administrator lockout: prevents self-lockout or removing last admin."""
    # 1. Anti-self-lockout
    if target_user.id == actor_id:
        raise InvalidStateTransitionError(
            f"Administrator anti-lockout protection: you cannot {action} your own account."
        )

    # 2. Prevent removing the last active administrator
    if target_user.role == PlatformRole.ADMIN.value:
        count_stmt = (
            select(func.count(User.id))
            .where(
                User.role == PlatformRole.ADMIN.value,
                User.access_status == AccessStatus.ACTIVE.value,
                User.is_active.is_(True),
            )
        )
        res = await session.execute(count_stmt)
        active_admin_count = res.scalar() or 0
        if active_admin_count <= 1:
            raise InvalidStateTransitionError(
                f"Administrator anti-lockout protection: cannot {action} the last remaining active administrator."
            )


async def transition_access_status(
    session: AsyncSession,
    target_user: User,
    new_status: AccessStatus | str,
    actor_id: str,
    actor_role: str,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, AuthAuditEvent]:
    """Execute a validated access status transition with audit logging and session termination."""
    current_status_val = target_user.access_status
    try:
        curr_enum = AccessStatus(current_status_val)
    except ValueError:
        curr_enum = AccessStatus.PENDING_REQUEST

    try:
        new_enum = AccessStatus(new_status)
    except ValueError:
        raise InvalidStateTransitionError(f"Unknown target access status: '{new_status}'")

    if curr_enum == new_enum:
        logger.info(f"User {target_user.id} is already in state '{new_enum.value}'; no transition needed.")
        # Return without audit record if no actual state change
        return target_user, None  # type: ignore

    rule = PERMITTED_TRANSITIONS.get((curr_enum, new_enum))
    if not rule:
        raise InvalidStateTransitionError(
            f"State transition from '{curr_enum.value}' to '{new_enum.value}' is not permitted."
        )

    # Check actor authorization
    is_admin = actor_role == PlatformRole.ADMIN.value
    actor_category = "admin" if is_admin else "user"
    if actor_category not in rule.allowed_actor_roles:
        raise InvalidStateTransitionError(
            f"Actor with role '{actor_role}' is not authorized to perform transition from "
            f"'{curr_enum.value}' to '{new_enum.value}'. Requires: {rule.allowed_actor_roles}"
        )

    # Anti-lockout checks if revoking an administrator
    if new_enum == AccessStatus.REVOKED and target_user.role == PlatformRole.ADMIN.value:
        await validate_admin_anti_lockout(session, target_user, "revoke", actor_id)

    # Apply state transition
    target_user.access_status = new_enum.value

    # If revoking, revoke all active sessions immediately
    if new_enum == AccessStatus.REVOKED:
        revoke_stmt = (
            update(UserSession)
            .where(UserSession.user_id == target_user.id)
            .values(is_revoked=True)
        )
        await session.execute(revoke_stmt)
        logger.warning(
            f"Revoked all active sessions for user {target_user.id} ({target_user.email}) due to access revocation."
        )

    # Record persistent audit event (NEVER log plaintext tokens or passwords)
    import json
    audit_details = {
        "previous_status": curr_enum.value,
        "new_status": new_enum.value,
        "reason": reason,
        **(metadata or {}),
    }

    audit_evt = AuthAuditEvent(
        id=generate_uuid("evt"),
        user_id=target_user.id,
        email=target_user.email,
        event_type=rule.event_type,
        success=True,
        actor_id=actor_id,
        details=json.dumps(audit_details),
        ip_address=client_ip,
        user_agent=user_agent[:255] if user_agent else None,
    )
    session.add(audit_evt)
    await session.flush()

    logger.info(
        f"Access transition executed for user {target_user.id}: {curr_enum.value} -> {new_enum.value} "
        f"[actor={actor_id}, event={rule.event_type}]"
    )
    return target_user, audit_evt

