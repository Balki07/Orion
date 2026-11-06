"""Automated test ensuring 100% route coverage in ORION's deny-by-default Route Policy Registry."""

import pytest
from app.main import app
from app.security.route_policy import (
    ROUTE_POLICY_MAP,
    ROUTE_POLICY_REGISTRY,
    get_route_policy,
    verify_all_routes_covered,
)


def test_all_routes_covered_in_policy_registry():
    """Verify that every APIRoute registered in FastAPI is explicitly declared in ROUTE_POLICY_REGISTRY."""
    missing = verify_all_routes_covered(app)
    assert not missing, f"The following routes lack an explicit security policy in ROUTE_POLICY_REGISTRY: {missing}"


def test_route_policy_map_consistency():
    """Verify that the policy map contains all policies without duplicates."""
    assert len(ROUTE_POLICY_MAP) == len(ROUTE_POLICY_REGISTRY)
    for policy in ROUTE_POLICY_REGISTRY:
        retrieved = get_route_policy(policy.method, policy.path)
        assert retrieved is not None
        assert retrieved.category == policy.category
        assert retrieved.auth_required == policy.auth_required


def test_public_routes_are_strictly_limited():
    """Verify that public routes without authentication are strictly intended public endpoints."""
    public_routes = [p for p in ROUTE_POLICY_REGISTRY if p.category == "public"]
    allowed_public_paths = {
        "/health",
        "/ready",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/invitations/redeem",
        "/api/v1/settings",
        "/api/v1/system/settings",
    }
    for p in public_routes:
        assert p.path in allowed_public_paths, f"Unexpected public route: {p.method} {p.path}"

