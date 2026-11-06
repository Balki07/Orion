"""User and Authentication Pydantic Schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.service import normalize_email, validate_password_strength


class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="Unique email address")
    password: str = Field(..., description="Plaintext password meeting strength requirements")
    display_name: str = Field(..., min_length=2, max_length=128, description="Display or researcher name")
    institution: str | None = Field(None, max_length=255, description="Academic or institutional affiliation")

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Display name must be at least 2 characters long.")
        return cleaned


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Account email address")
    password: str = Field(..., min_length=1, max_length=128, description="Account password")

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, v: str) -> str:
        return normalize_email(v)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    institution: str | None = None
    status: str
    is_active: bool
    role: str = "researcher"
    access_status: str = "pending_request"
    created_at: datetime


class AuthSessionResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128, description="Current plaintext password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New plaintext password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(None, min_length=2, max_length=128)
    institution: str | None = Field(None, max_length=255)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if len(cleaned) < 2:
                raise ValueError("Display name must be at least 2 characters long.")
            return cleaned
        return v


class SessionItemResponse(BaseModel):
    id: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    is_active: bool
    is_current: bool = False


