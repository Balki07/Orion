"""Pydantic schemas for Researcher Access Control, Access Requests, and Invitations."""

from datetime import datetime
from pydantic import BaseModel, Field


class AccessRequestCreate(BaseModel):
    """Payload for submitting or re-submitting a research access request."""

    institution: str | None = Field(default=None, max_length=255)
    research_purpose: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of intended research topic, methodology, and institutional context.",
    )
    intended_data_types: str | None = Field(default=None, max_length=255)


class AccessRequestResponse(BaseModel):
    """Public/Admin representation of a research access request."""

    id: str
    user_id: str
    user_email: str | None = None
    user_display_name: str | None = None
    institution: str | None = None
    research_purpose: str
    intended_data_types: str | None = None
    status: str  # "pending", "approved", "rejected"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessRequestApprove(BaseModel):
    """Payload for administrator approval of an access request."""

    expires_in_days: int = Field(default=14, ge=1, le=90)


class AccessRequestReject(BaseModel):
    """Payload for administrator rejection of an access request."""

    reason: str = Field(default="Access request declined by administrator.", max_length=500)


class InvitationCreate(BaseModel):
    """Payload for direct administrator invitation creation."""

    user_id: str
    expires_in_days: int = Field(default=14, ge=1, le=90)


class InvitationResponse(BaseModel):
    """Representation of an issued researcher invitation."""

    id: str
    user_id: str
    user_email: str | None = None
    invitation_token: str | None = None  # Cleartext token provided ONLY at creation time!
    expires_at: datetime
    is_redeemed: bool
    redeemed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RedeemInvitationRequest(BaseModel):
    """Payload for redeeming an approved invitation token."""

    invitation_token: str = Field(..., min_length=16, description="Cryptographic invitation token")


class UserRoleUpdate(BaseModel):
    """Payload for administrative role update with anti-lockout protection."""

    role: str = Field(..., pattern="^(admin|researcher)$")


class UserStatusAction(BaseModel):
    """Payload for admin status actions (revoke/reactivate)."""

    reason: str | None = Field(default=None, max_length=500)

