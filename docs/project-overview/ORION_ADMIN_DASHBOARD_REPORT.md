# ORION — Admin Dashboard & Researcher Usage Analytics Report

**Status:** Implementation Complete & Fully Verified  
**Date:** November 5, 2026  
**Audience:** Platform Architects, Security Engineers, DevOps, System Administrators

---

## 1. Executive Summary

A secure, multi-dimensional **Admin Dashboard & Researcher Usage Analytics** console (`/admin`) has been architected and implemented for ORION. The console provides platform administrators with real-time operational oversight across registered researchers, authentication security audit events, cumulative per-user storage compliance (500 MB pilot quota), Gemini AI request volume and token consumption, and system infrastructure readiness.

The implementation strictly honors ORION's multi-user isolation guarantees, "zero secrets leakage" principle, and Reading Room design aesthetic. Non-administrative users and unauthenticated callers are barred from administrative interfaces at both the network API layer and the frontend routing layer.

---

## 2. Admin Authorization Architecture & Security Safeguards

### 2.1 Principle of Least Privilege & Anti-Self-Promotion
1. **Dynamic Backend Authorization:** All administrative endpoints under `/api/v1/admin/` enforce the FastAPI dependency `require_admin_user`, which verifies `AuthenticatedUser.is_admin`.
2. **Deterministic Role Resolution:** Administrative status cannot be requested, self-assigned, or altered by normal mutation payloads. It is strictly resolved from:
   - Configured administrative email addresses (`settings.ADMIN_EMAILS`, e.g., `admin@orion-assistant.ai`).
   - Configured administrative unique identifiers (`settings.ADMIN_USER_IDS`, e.g., `user_admin_001`).
3. **HTTP Status Code Separation:**
   - Unauthenticated requests receive `HTTP 401 Unauthorized` (`AuthenticationRequiredError`).
   - Authenticated non-administrative researchers receive `HTTP 403 Forbidden` (`UnauthorizedAccessError`).
4. **Data Isolation & Confidentiality:**
   - Administrators can inspect researcher metadata, cumulative storage bytes, document counts, and audit logs.
   - Private document text, chunk content, vector embeddings, and session notes of researchers are **never exposed or leaked** via admin endpoints.
   - Plaintext passwords, Argon2id hashes, session tokens, and Gemini API keys are completely stripped and excluded from all responses.

---

## 3. Persistent Authentication Audit Log (`AuthAuditEvent`)

### 3.1 Model Schema & Alembic Migration
To satisfy security oversight requirements without compromising credential confidentiality, a dedicated audit table `auth_audit_events` was created via `app.models.auth_event.AuthAuditEvent` and Alembic migration `0003_create_auth_audit_events_table.py` (`down_revision = "0002_research_domain"`).

```sql
CREATE TABLE auth_audit_events (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(255),
    event_type VARCHAR(32) NOT NULL, -- 'login_success', 'login_failure', 'logout', 'register'
    success BOOLEAN NOT NULL DEFAULT TRUE,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    failure_reason VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_auth_events_user_time ON auth_audit_events(user_id, created_at);
CREATE INDEX ix_auth_events_type_time ON auth_audit_events(event_type, created_at);
```

### 3.2 Audit Event Interception Points
- **Registration (`/auth/register`):** Logs a successful registration audit event with client IP and User-Agent.
- **Login (`/auth/login`):**
  - Logs `login_failure` (`failure_reason = "RATE_LIMIT_EXCEEDED"`) when threshold is reached.
  - Logs `login_failure` (`failure_reason = "INVALID_CREDENTIALS"`) when password hash or account lookup fails.
  - Logs `login_failure` (`failure_reason = "ACCOUNT_DISABLED"`) when inactive/suspended.
  - Logs `login_success` with sanitized client metadata on credential verification.
- **Logout (`/auth/logout`):** Logs session revocation and logout completion.

---

## 4. Backend Admin REST API (`/api/v1/admin`)

| Endpoint | Method | Response Schema | Description |
| :--- | :---: | :--- | :--- |
| `/api/v1/admin/overview` | `GET` | `AdminOverviewResponse` | High-level metrics across Users, Logins, Document Storage, and AI Usage. |
| `/api/v1/admin/users` | `GET` | `AdminUserListResponse` | Paginated, searchable researcher list with batch aggregated storage, login, and AI metrics (zero N+1 queries). |
| `/api/v1/admin/users/{user_id}` | `GET` | `AdminUserDetailResponse` | Comprehensive researcher profile, 500 MB quota utilization, recent logins, documents, and active sessions. |
| `/api/v1/admin/users/{user_id}/activity` | `GET` | `list[dict]` | Unified chronological activity timeline (auth events, doc uploads, AI QA calls). |
| `/api/v1/admin/users/{user_id}/usage` | `GET` | `dict` | Detailed breakdown of storage quota and LLM token volume for a specific researcher. |
| `/api/v1/admin/analytics/registrations` | `GET` | `list[TimeSeriesPoint]` | Daily researcher registration volume over past 14/30 days. |
| `/api/v1/admin/analytics/logins` | `GET` | `list[LoginTimeSeriesPoint]` | Daily successful vs failed login events for engagement and threat monitoring. |
| `/api/v1/admin/analytics/documents` | `GET` | `list[TimeSeriesPoint]` | Daily document ingestion activity. |
| `/api/v1/admin/analytics/ai-usage` | `GET` | `list[DailyAIUsagePoint]` | Daily Gemini API calls, token counts, and estimated cost tracking. |
| `/api/v1/admin/system-health` | `GET` | `AdminSystemHealth` | Infrastructure health check (Backend, DB dialect, pgvector readiness, S3/local storage, durable ingestion worker, Gemini RPM). |

---

## 5. Frontend Admin Interface (`/admin`)

### 5.1 Architecture & Role-Gated Navigation
- **Sidebar Integration:** In `frontend/src/components/layout/Sidebar.tsx`, the **Admin Console** navigation item (`ShieldAlert` icon) is conditionally rendered only when `user?.role === 'admin'`.
- **Route Guarding:** In `frontend/src/App.tsx`, selecting `#admin` or `/admin` checks `user?.role === 'admin'`. If a non-admin attempts access, an **Access Restricted** fallback banner is rendered with a direct return action to the researcher dashboard.

### 5.2 Interface Views & Capabilities
1. **Executive Overview Tab:**
   - 4 Top Metric Cards: Registered Researchers, Total Logins (with failure count), Cumulative Document Storage (MB), and Gemini AI Calls (tokens & estimated cost).
   - Trend Visualization: Researcher Onboarding bar chart (past 14 days), Authentication Volume (Success vs Failed attempts) stacked bar chart, Gemini Model distribution breakdown, and standard storage quota compliance.
2. **Researcher Directory Tab:**
   - Searchable by name or email with instant filtering.
   - Filterable by account status (`active`, `suspended`, `inactive`) and role (`admin`, `authenticated`).
   - Interactive table detailing researcher name, role badge, status badge, 500 MB storage usage with visual progress bar, AI query count/tokens, and login frequency.
   - Pagination controls (`Previous`, `Page X of Y`, `Next`).
3. **Researcher Detail Modal (`AdminUserDetailModal`):**
   - Opened by clicking any researcher in the directory.
   - Displays 500 MB quota progress gauge (with color shifts: emerald `<75%`, amber `75–89%`, rose `≥90%`).
   - Tabbed sub-views: *Overview & Active Sessions*, *Indexed Documents*, *Recent Login Audit Events*, and *Unified Chronological Timeline*.
4. **Infrastructure & System Health Tab:**
   - Real-time status cards for FastAPI Application Backend, PostgreSQL/SQLite with pgvector search readiness, Object Storage Provider (S3/local), Durable Ingestion Worker concurrency, and Gemini LLM integration with RPM limits.
5. **Authentication Security Stream Tab:**
   - Explains the Zero Secrets Principle and provides quick navigation to audited researcher events.

---

## 6. Automated Validation & Evidence Rigor

All components have been verified via automated test suites without mocking real backend routes or simulating metrics.

### 6.1 Backend Test Results (`backend/tests/test_admin_dashboard.py`)
Command: `pytest backend/tests/test_admin_dashboard.py -v`
```
backend/tests/test_admin_dashboard.py::test_admin_access_allowed_and_overview_metrics PASSED [ 11%]
backend/tests/test_admin_dashboard.py::test_non_admin_forbidden PASSED                       [ 22%]
backend/tests/test_admin_dashboard.py::test_unauthenticated_unauthorized PASSED              [ 33%]
backend/tests/test_admin_dashboard.py::test_login_audit_events_recording PASSED             [ 44%]
backend/tests/test_admin_dashboard.py::test_user_pagination_search_and_filters PASSED       [ 55%]
backend/tests/test_admin_dashboard.py::test_user_detail_and_no_leak_of_private_content PASSED [ 66%]
backend/tests/test_admin_dashboard.py::test_time_series_analytics_endpoints PASSED          [ 77%]
backend/tests/test_admin_dashboard.py::test_system_health_safe_status PASSED                 [ 88%]
backend/tests/test_admin_dashboard.py::test_user_activity_and_usage_breakdown PASSED        [100%]

============================= 9 passed in 13.70s ==============================
```

### 6.2 Full Regression Test Suite
Command: `pytest backend/tests/test_admin_dashboard.py backend/tests/test_auth_backend.py backend/tests/test_csrf_document_upload.py backend/tests/test_storage_governance.py`
```
backend/tests/test_admin_dashboard.py .........                          [ 20%]
backend/tests/test_auth_backend.py .................                     [ 57%]
backend/tests/test_csrf_document_upload.py .......                       [ 73%]
backend/tests/test_storage_governance.py ............                    [100%]

================= 45 passed, 4 warnings in 121.24s (0:02:01) ==================
```

### 6.3 Frontend Unit and Component Suite
Command: `vitest run tests/AdminDashboard.test.tsx`
```
 ✓ tests/AdminDashboard.test.tsx (3 tests) 1406ms
   ✓ Admin Dashboard UI Component Tests > renders executive overview metrics with correct values 396ms
   ✓ Admin Dashboard UI Component Tests > switches to Researcher Directory and displays user data with 500 MB quota 707ms
   ✓ Admin Dashboard UI Component Tests > switches to Infrastructure & Health tab and displays readiness 303ms

 Test Files  1 passed (1)
      Tests  3 passed (3)
```

Full frontend test run:
```
 Test Files  13 passed (13)
      Tests  92 passed (92)
```

### 6.4 Production TypeScript Build
Command: `npm --prefix frontend run build`
```
> frontend@0.1.0 build
> tsc -b && vite build

vite v5.4.21 building for production...
✓ 2355 modules transformed.
dist/index.html                                                    1.28 kB │ gzip:   0.64 kB
dist/assets/index-D2ddLxUE.css                                    76.68 kB │ gzip:  20.23 kB
dist/assets/index-M96E3ZqI.js                                    912.59 kB │ gzip: 263.99 kB
✓ built in 32.89s
```

---

## 7. Migration Notes for Cloud Environments

- **Local/Staging (SQLite):** Tables are automatically initialized upon startup via `Base.metadata.create_all()`.
- **Aiven Production PostgreSQL:** The Alembic migration `0003_create_auth_audit_events_table.py` is safely drafted and ready. In accordance with ORION governance rules, this migration was **not applied** to the active Aiven PostgreSQL instance during development.

