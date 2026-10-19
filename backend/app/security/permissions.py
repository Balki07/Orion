"""ORION Ownership and Access Control verification."""

from app.core.errors import UnauthorizedAccessError


def verify_ownership(resource_owner_id: str, current_user_id: str, resource_type: str = "resource") -> None:
    """Ensure that the current user owns the target resource."""
    if resource_owner_id != current_user_id:
        raise UnauthorizedAccessError(
            f"You do not have permission to access or modify this {resource_type}."
        )
