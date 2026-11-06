"""Deny-by-Default Route Policy Registry and Coverage Verification for ORION."""

from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI
from fastapi.routing import APIRoute

PolicyCategory = Literal["public", "authenticated", "active_researcher", "admin", "public_demo"]


@dataclass(frozen=True)
class RoutePolicy:
    """Explicit authorization policy required for a route."""

    method: str
    path: str
    category: PolicyCategory
    required_role: str | None
    required_access_status: str | None
    auth_required: bool
    purpose: str


# Complete registry covering every route in ORION
ROUTE_POLICY_REGISTRY: list[RoutePolicy] = [
    # --- Public & Health Probes ---
    RoutePolicy("GET", "/health", "public", None, None, False, "System liveness probe"),
    RoutePolicy("GET", "/ready", "public", None, None, False, "Infrastructure readiness probe (DB, pgvector, S3, embedder)"),

    # --- Public Auth & Invitation Redemption ---
    RoutePolicy("POST", "/api/v1/auth/register", "public", None, None, False, "Public researcher registration"),
    RoutePolicy("POST", "/api/v1/auth/login", "public", None, None, False, "Account login and JWT session cookie issuance"),
    RoutePolicy("POST", "/api/v1/auth/invitations/redeem", "public", None, None, False, "Redeem cryptographic invitation token to activate researcher access"),

    # --- Public Demo Endpoints (Isolated Curated EPR Corpus) ---
    RoutePolicy("GET", "/api/v1/demo/status", "public_demo", None, None, False, "Public demo status and capacity probe"),
    RoutePolicy("GET", "/api/v1/demo/papers", "public_demo", None, None, False, "List approved open-access demo research papers"),
    RoutePolicy("GET", "/api/v1/demo/papers/{document_id}", "public_demo", None, None, False, "Get single demo paper metadata"),
    RoutePolicy("GET", "/api/v1/demo/papers/{document_id}/pdf", "public_demo", None, None, False, "Stream authentic demo paper PDF binary"),
    RoutePolicy("GET", "/api/v1/demo/papers/{document_id}/pages/{page_number}", "public_demo", None, None, False, "Get extracted text for a specific demo paper page"),
    RoutePolicy("GET", "/api/v1/demo/examples", "public_demo", None, None, False, "List curated example research questions"),
    RoutePolicy("POST", "/api/v1/demo/ask", "public_demo", None, None, False, "Evidence-grounded question answering over demo corpus"),

    # --- Authenticated User Operations (Available to Pending/Revoked Accounts) ---
    RoutePolicy("GET", "/api/v1/auth/me", "authenticated", None, None, True, "Get current user account, role, and access status"),
    RoutePolicy("POST", "/api/v1/auth/logout", "authenticated", None, None, True, "Terminate current session and clear cookies"),
    RoutePolicy("POST", "/api/v1/auth/access-request", "authenticated", None, None, True, "Submit or re-submit research access request"),
    RoutePolicy("GET", "/api/v1/auth/access-request", "authenticated", None, None, True, "View own access request status"),
    RoutePolicy("POST", "/api/v1/auth/change-password", "authenticated", None, None, True, "Update account password with Argon2id"),
    RoutePolicy("PATCH", "/api/v1/auth/profile", "authenticated", None, None, True, "Update researcher display name or affiliation"),
    RoutePolicy("GET", "/api/v1/auth/sessions", "authenticated", None, None, True, "List own active login sessions"),
    RoutePolicy("POST", "/api/v1/auth/sessions/revoke-others", "authenticated", None, None, True, "Revoke all own sessions except current"),

    # --- System Settings Metadata ---
    RoutePolicy("GET", "/api/v1/settings", "active_researcher", "researcher", "active", True, "Legitimate researcher workspace settings and limits"),
    RoutePolicy("GET", "/api/v1/settings/system", "admin", "admin", "active", True, "Administrative system diagnostics and model configurations"),
    RoutePolicy("GET", "/api/v1/system/settings", "admin", "admin", "active", True, "Alias for administrative system diagnostics"),

    # --- Active Researcher Endpoints (Active Researchers + Administrators) ---
    # Usage & Quotas (Own Account)
    RoutePolicy("GET", "/api/v1/usage", "active_researcher", "researcher", "active", True, "View own workspace usage and document counts"),
    RoutePolicy("GET", "/api/v1/settings/llm-quota", "active_researcher", "researcher", "active", True, "View active Gemini LLM quota limits and usage"),
    RoutePolicy("GET", "/api/v1/llm-quota", "active_researcher", "researcher", "active", True, "Alias for LLM quota view"),
    RoutePolicy("GET", "/api/v1/settings/llm-quota/estimate", "active_researcher", "researcher", "active", True, "Estimate remaining question budget under quota"),
    RoutePolicy("GET", "/api/v1/llm-quota/estimate", "active_researcher", "researcher", "active", True, "Alias for question budget estimate"),

    # Document Management (Own Account)
    RoutePolicy("POST", "/api/v1/documents", "active_researcher", "researcher", "active", True, "Upload and enqueue single PDF paper"),
    RoutePolicy("POST", "/api/v1/documents/batch", "active_researcher", "researcher", "active", True, "Upload multiple PDF papers in batch"),
    RoutePolicy("GET", "/api/v1/documents", "active_researcher", "researcher", "active", True, "List own uploaded research documents"),
    RoutePolicy("GET", "/api/v1/documents/storage-usage", "active_researcher", "researcher", "active", True, "Check own cumulative 500 MB storage allocation"),
    RoutePolicy("GET", "/api/v1/documents/{document_id}", "active_researcher", "researcher", "active", True, "Get own document metadata"),
    RoutePolicy("GET", "/api/v1/documents/{document_id}/status", "active_researcher", "researcher", "active", True, "Poll own document ingestion pipeline status"),
    RoutePolicy("GET", "/api/v1/documents/{document_id}/pages/{page_number}", "active_researcher", "researcher", "active", True, "Get extracted text of own document page"),
    RoutePolicy("GET", "/api/v1/documents/{document_id}/file", "active_researcher", "researcher", "active", True, "Download own raw PDF file"),
    RoutePolicy("GET", "/api/v1/documents/{document_id}/pages/{page_number}/render", "active_researcher", "researcher", "active", True, "Download rendered PNG page thumbnail"),
    RoutePolicy("POST", "/api/v1/documents/{document_id}/retry", "active_researcher", "researcher", "active", True, "Retry failed ingestion for own document"),
    RoutePolicy("DELETE", "/api/v1/documents/{document_id}", "active_researcher", "researcher", "active", True, "Delete own document, chunks, and storage files"),

    # Collections (Own Account)
    RoutePolicy("POST", "/api/v1/collections", "active_researcher", "researcher", "active", True, "Create own document collection"),
    RoutePolicy("GET", "/api/v1/collections", "active_researcher", "researcher", "active", True, "List own document collections"),
    RoutePolicy("GET", "/api/v1/collections/{collection_id}", "active_researcher", "researcher", "active", True, "Get own collection details"),
    RoutePolicy("PATCH", "/api/v1/collections/{collection_id}", "active_researcher", "researcher", "active", True, "Update own collection name/description"),
    RoutePolicy("DELETE", "/api/v1/collections/{collection_id}", "active_researcher", "researcher", "active", True, "Delete own document collection"),
    RoutePolicy("POST", "/api/v1/collections/{collection_id}/documents", "active_researcher", "researcher", "active", True, "Add or remove documents in own collection"),

    # Research Synthesis & Chat (Own Account)
    RoutePolicy("POST", "/api/v1/research/ask", "active_researcher", "researcher", "active", True, "Execute evidence-grounded research query"),
    RoutePolicy("POST", "/api/v1/research/ask/stream", "active_researcher", "researcher", "active", True, "Execute streaming research query with continuous auth checks"),
    RoutePolicy("POST", "/api/v1/research/compare", "active_researcher", "researcher", "active", True, "Synthesize multi-paper comparison matrix"),
    RoutePolicy("POST", "/api/v1/research/sessions", "active_researcher", "researcher", "active", True, "Create new research session"),
    RoutePolicy("GET", "/api/v1/research/sessions", "active_researcher", "researcher", "active", True, "List own research chat sessions"),
    RoutePolicy("GET", "/api/v1/research/sessions/{session_id}", "active_researcher", "researcher", "active", True, "Get own research chat session with messages"),
    RoutePolicy("PATCH", "/api/v1/research/sessions/{session_id}", "active_researcher", "researcher", "active", True, "Rename own research session"),
    RoutePolicy("DELETE", "/api/v1/research/sessions/{session_id}", "active_researcher", "researcher", "active", True, "Delete own research session"),
    RoutePolicy("POST", "/api/v1/research/messages/{message_id}/feedback", "active_researcher", "researcher", "active", True, "Submit feedback/rating on chat answer"),

    # Research Notes (Own Account)
    RoutePolicy("POST", "/api/v1/notes", "active_researcher", "researcher", "active", True, "Create own research note"),
    RoutePolicy("GET", "/api/v1/notes", "active_researcher", "researcher", "active", True, "List own research notes"),
    RoutePolicy("GET", "/api/v1/notes/{note_id}", "active_researcher", "researcher", "active", True, "Get own research note"),
    RoutePolicy("PATCH", "/api/v1/notes/{note_id}", "active_researcher", "researcher", "active", True, "Update own research note"),
    RoutePolicy("DELETE", "/api/v1/notes/{note_id}", "active_researcher", "researcher", "active", True, "Delete own research note"),
    RoutePolicy("GET", "/api/v1/notes/{note_id}/export", "active_researcher", "researcher", "active", True, "Export own note as Markdown or HTML"),

    # --- Administrator Oversight Endpoints (Admin Only) ---
    RoutePolicy("PUT", "/api/v1/settings/llm-quota", "admin", "admin", "active", True, "Update global LLM quota parameters"),
    RoutePolicy("PUT", "/api/v1/llm-quota", "admin", "admin", "active", True, "Alias for global LLM quota update"),
    RoutePolicy("GET", "/api/v1/admin/overview", "admin", "admin", "active", True, "Executive overview metrics and system statistics"),
    RoutePolicy("GET", "/api/v1/admin/users", "admin", "admin", "active", True, "Directory of registered users with role and access status"),
    RoutePolicy("GET", "/api/v1/admin/users/{user_id}", "admin", "admin", "active", True, "User account metadata details (no private research content)"),
    RoutePolicy("GET", "/api/v1/admin/users/{user_id}/activity", "admin", "admin", "active", True, "Audit trail of logins and security events for user"),
    RoutePolicy("GET", "/api/v1/admin/users/{user_id}/usage", "admin", "admin", "active", True, "Aggregated document counts and storage usage for user"),
    RoutePolicy("POST", "/api/v1/admin/users/{user_id}/revoke", "admin", "admin", "active", True, "Revoke researcher access with anti-lockout protection"),
    RoutePolicy("POST", "/api/v1/admin/users/{user_id}/reactivate", "admin", "admin", "active", True, "Reactivate revoked researcher access"),
    RoutePolicy("POST", "/api/v1/admin/users/{user_id}/role", "admin", "admin", "active", True, "Update user role (admin/researcher) with anti-lockout"),
    RoutePolicy("POST", "/api/v1/admin/users/{user_id}/direct-activate", "admin", "admin", "active", True, "Directly activate pending user account"),
    RoutePolicy("GET", "/api/v1/admin/access-requests", "admin", "admin", "active", True, "List researcher access requests"),
    RoutePolicy("POST", "/api/v1/admin/access-requests/{request_id}/approve", "admin", "admin", "active", True, "Approve access request and issue invitation"),
    RoutePolicy("POST", "/api/v1/admin/access-requests/{request_id}/reject", "admin", "admin", "active", True, "Reject researcher access request"),
    RoutePolicy("GET", "/api/v1/admin/invitations", "admin", "admin", "active", True, "List issued researcher invitations"),
    RoutePolicy("POST", "/api/v1/admin/invitations", "admin", "admin", "active", True, "Directly create researcher invitation"),
    RoutePolicy("DELETE", "/api/v1/admin/invitations/{invitation_id}", "admin", "admin", "active", True, "Cancel/revoke issued researcher invitation"),
    RoutePolicy("GET", "/api/v1/admin/analytics/registrations", "admin", "admin", "active", True, "User registration analytics time series"),
    RoutePolicy("GET", "/api/v1/admin/analytics/logins", "admin", "admin", "active", True, "Login activity analytics time series"),
    RoutePolicy("GET", "/api/v1/admin/analytics/documents", "admin", "admin", "active", True, "Document ingestion analytics time series"),
    RoutePolicy("GET", "/api/v1/admin/analytics/ai-usage", "admin", "admin", "active", True, "Gemini AI usage analytics time series"),
    RoutePolicy("GET", "/api/v1/admin/system-health", "admin", "admin", "active", True, "Technical diagnostics and infrastructure health"),
]


# Lookup dictionary: (method, normalized_path) -> RoutePolicy
ROUTE_POLICY_MAP: dict[tuple[str, str], RoutePolicy] = {
    (p.method.upper(), p.path): p for p in ROUTE_POLICY_REGISTRY
}


def get_route_policy(method: str, path: str) -> RoutePolicy | None:
    """Retrieve the declared policy for a given HTTP method and path."""
    return ROUTE_POLICY_MAP.get((method.upper(), path))


def verify_all_routes_covered(app: FastAPI) -> list[str]:
    """Inspect all registered APIRoutes in the FastAPI app and verify 100% coverage.

    Returns a list of missing route identifiers (METHOD path). If empty, all routes are covered.
    """
    missing_routes: list[str] = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        # Skip OpenAPI docs/schema
        if route.path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            continue

        for method in route.methods:
            if method.upper() == "HEAD":
                continue  # HEAD is automatically generated by FastAPI for GET
            if (method.upper(), route.path) not in ROUTE_POLICY_MAP:
                missing_routes.append(f"{method.upper()} {route.path}")

    return missing_routes

