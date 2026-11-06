"""ORION centralized application errors and exception models."""

from typing import Any

from fastapi import HTTPException, status


class OrionException(HTTPException):
    """Base exception for all ORION application errors."""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        detail: str = "An unexpected error occurred in ORION.",
        meta: dict[str, Any] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.meta = meta or {}


class DocumentNotFoundError(OrionException):
    def __init__(self, document_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DOCUMENT_NOT_FOUND",
            detail=f"Document with ID '{document_id}' was not found.",
            meta={"document_id": document_id},
        )


class CollectionNotFoundError(OrionException):
    def __init__(self, collection_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="COLLECTION_NOT_FOUND",
            detail=f"Collection with ID '{collection_id}' was not found.",
            meta={"collection_id": collection_id},
        )


class NoteNotFoundError(OrionException):
    def __init__(self, note_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOTE_NOT_FOUND",
            detail=f"Note with ID '{note_id}' was not found.",
            meta={"note_id": note_id},
        )


class UnauthorizedAccessError(OrionException):
    def __init__(self, detail: str = "You do not have permission to access this resource."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ACCESS",
            detail=detail,
        )


class AuthenticationRequiredError(OrionException):
    def __init__(self, detail: str = "Authentication credentials were not provided or are invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            detail=detail,
        )


class IngestionError(OrionException):
    def __init__(
        self,
        detail: str,
        stage: str,
        document_id: str | None = None,
        error_code: str | None = None,
    ):
        code = error_code or f"INGESTION_FAILED_{stage.upper()}"
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            detail=detail,
            meta={"stage": stage, "document_id": document_id, "error_code": code},
        )
        self.error_code = code


class InsufficientEvidenceError(OrionException):
    def __init__(self, detail: str = "No sufficient retrieved evidence found to answer the query."):
        super().__init__(
            status_code=status.HTTP_200_OK,
            code="INSUFFICIENT_EVIDENCE",
            detail=detail,
        )


class FileValidationError(OrionException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_FILE_UPLOAD",
            detail=detail,
        )


class DuplicateEmailError(OrionException):
    def __init__(self, detail: str = "An account with this email address already exists."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_EMAIL",
            detail=detail,
        )


class InvalidCredentialsError(OrionException):
    def __init__(self, detail: str = "Invalid email or password."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            detail=detail,
        )


class AccountDisabledError(OrionException):
    def __init__(self, detail: str = "This account has been deactivated."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCOUNT_DISABLED",
            detail=detail,
        )


class RateLimitExceededError(OrionException):
    def __init__(self, detail: str = "Too many attempts. Please try again later."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            detail=detail,
        )


class CSRFValidationError(OrionException):
    def __init__(self, detail: str = "CSRF verification failed. Missing or invalid CSRF token."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CSRF_VALIDATION_FAILED",
            detail=detail,
        )


class StorageQuotaExceededError(OrionException):
    def __init__(
        self,
        detail: str,
        current_bytes: int | None = None,
        quota_bytes: int | None = None,
        remaining_bytes: int | None = None,
        requested_bytes: int | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="STORAGE_QUOTA_EXCEEDED",
            detail=detail,
            meta={
                "current_bytes": current_bytes,
                "quota_bytes": quota_bytes,
                "remaining_bytes": remaining_bytes,
                "requested_bytes": requested_bytes,
            },
        )


class AccessRestrictedError(OrionException):
    """Raised when an authenticated user attempts research operations without active status."""

    def __init__(self, reason_code: str, detail: str | None = None):
        messages = {
            "access_pending": "Your research access is pending administrator review.",
            "access_rejected": "Your research access request has been declined.",
            "access_revoked": "Your research access has been revoked.",
            "invitation_pending": "Your access has been approved; invitation redemption is required to activate your workspace.",
        }
        msg = detail or messages.get(reason_code, "Research access is restricted for this account.")
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=reason_code,
            detail=msg,
        )


class InvalidStateTransitionError(OrionException):
    """Raised when an illegal or unauthorized access status transition is requested."""

    def __init__(self, detail: str = "Invalid account access status transition."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_STATE_TRANSITION",
            detail=detail,
        )

