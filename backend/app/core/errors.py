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
    def __init__(self, detail: str, stage: str, document_id: str | None = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=f"INGESTION_FAILED_{stage.upper()}",
            detail=detail,
            meta={"stage": stage, "document_id": document_id},
        )


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
