# ORION — Phase 6B: Storage Governance & Production Storage Readiness Report

## Executive Summary

Phase 6B introduces cumulative per-user storage governance and strengthens production S3 storage readiness across the ORION application without degrading existing multi-tenant database isolation or modifying live Aiven PostgreSQL records.

The pilot storage limit is standardized to **500 MB per user**, managed through a centralized configuration setting, enforced across both single-file and batch upload request handlers, protected against concurrent quota-exhaustion race conditions, and presented through an ambient cream-and-amber storage meter in the frontend Document Library.

---

## 1. Architectural Changes

### 1.1 Centralized Storage Quota Configuration
In `backend/app/core/config.py`:
- Added `USER_STORAGE_QUOTA_MB: int = 500` under Ingestion & Upload Caps.
- Implemented `@property def user_storage_quota_bytes(self) -> int` computing dynamic byte limit (`500 * 1024 * 1024 = 524,288,000` bytes).
- Hardened `validate_production_requirements()`: when `ENVIRONMENT=production`, mandates `STORAGE_PROVIDER == "s3"` and requires non-empty `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`, failing fast on startup with `RuntimeError` without logging secret credentials.

### 1.2 Storage Lifecycle & Accounting
In `backend/app/api/v1/documents.py`:
- Helper `get_user_storage_usage(user_id: str, db: AsyncSession) -> tuple[int, int]`: executes an aggregate query on `documents` table:
  ```sql
  SELECT COALESCE(SUM(file_size), 0), COUNT(id)
  FROM documents
  WHERE owner_id = :user_id AND status != 'failed';
  ```
- **Lifecycle Guarantees**:
  - Documents with `status == "failed"` are excluded from storage usage accounting.
  - Deleted documents (`DELETE /api/v1/documents/{id}`) remove the database record and purge object prefixes from storage (`{user_id}/{document_id}`), instantly freeing capacity for new uploads.

### 1.3 Concurrency & Race-Condition Defense
- In-memory event-loop locks (`_user_upload_locks = dict[str, asyncio.Lock]`) serialize concurrent requests from the same user within worker processes.
- Database row locking (`SELECT id FROM users WHERE id = :user_id FOR UPDATE`) serializes transactions across multiple backend instances when connected to PostgreSQL.
- Over-quota upload attempts are rejected with `HTTP 413` (`StorageQuotaExceededError`) before writing any bytes to storage backends.
- Detailed, user-friendly error messages explain:
  - Current usage (e.g. `12.40 MB`).
  - Quota limit (`500 MB`).
  - Remaining capacity (`487.60 MB`).
  - Size of rejected file (`32.00 MB`).

### 1.4 Authenticated Storage Usage API
- Endpoint: `GET /api/v1/documents/storage-usage`
- Mounted before `GET /documents/{document_id}` to prevent route collision.
- Response Schema (`StorageUsageResponse`):
  ```json
  {
    "total_quota_bytes": 524288000,
    "used_storage_bytes": 13002342,
    "remaining_storage_bytes": 511285658,
    "usage_percentage": 2.48,
    "document_count": 8,
    "quota_mb": 500
  }
  ```
- Strict user-isolation: only returns statistics for the authenticated caller; unauthenticated requests are rejected.

### 1.5 Storage Readiness Probes & Secret Protection
- Added abstract method `check_readiness() -> bool` to `StorageService` (`backend/app/services/storage/base.py`).
- `LocalStorageService.check_readiness()` verifies that local upload directory exists and is a directory.
- `S3StorageService.check_readiness()` calls `head_bucket()` via `boto3`.
- `health.py` (`GET /ready`): verifies storage readiness and reports `"ready (s3)"` or `"unhealthy: storage access check failed"` without leaking bucket names, endpoints, or AWS access credentials in responses or error logs.

---

## 2. Frontend Implementation

### 2.1 Storage Meter Card (`DocumentLibrary.tsx`)
- Rendered prominently above search and filter controls in `DocumentLibrary.tsx`.
- Designed with ORION Reading Room aesthetic (cream parchment background, subtle borders, amber accents).
- Displays:
  - Header: `User Storage Quota` with `500 MB Pilot Cap` badge.
  - Current usage: `{usedMB} / {quotaMB} MB ({percentage}%)` with remaining capacity and document count.
  - Progress bar: dynamic gradient transitioning from `navy-700` (< 80%) to `amber-600` (80–94%) and `red-600` (>= 95%).
  - Warning banner: appears when storage usage reaches or exceeds 80%, providing warning guidance before limits are reached.
- Automatically refreshes on:
  - Initial view load.
  - Manual document refresh button click.
  - Successful upload modal submission (`onUploadSuccess`).
  - Successful document deletion.
  - Asynchronous background polling completion.

### 2.2 Client Integration (`api.ts` & `types/index.ts`)
- Added `StorageUsageResponse` interface to `frontend/src/types/index.ts`.
- Added `api.getStorageUsage()` method to `frontend/src/services/api.ts`.

---

## 3. Verification & Test Outcomes

### 3.1 Dedicated Storage Governance Test Suite (`test_storage_governance.py`)
All 12 test specifications were implemented and passed cleanly:

| # | Test Case | Target Requirement | Outcome |
|---|---|---|---|
| 1 | `test_01_user_below_quota_can_upload` | User below 500 MB uploads successfully | **PASSED** |
| 2 | `test_02_user_at_quota_cannot_upload_more` | User at quota rejected with HTTP 413 | **PASSED** |
| 3 | `test_03_user_exceeding_quota_receives_remaining_capacity_details` | HTTP 413 response includes usage, quota, and capacity details | **PASSED** |
| 4 | `test_04_batch_uploads_enforce_aggregate_quota` | Batch upload enforces cumulative quota across files | **PASSED** |
| 5 | `test_05_concurrent_uploads_cannot_bypass_quota` | Concurrent race conditions cannot bypass quota limit | **PASSED** |
| 6 | `test_06_independent_quotas_between_users` | Tenant quotas are completely isolated and independent | **PASSED** |
| 7 | `test_07_failed_and_deleted_document_storage_accounting` | Deleted and failed documents do not consume storage quota | **PASSED** |
| 8 | `test_08_storage_usage_api_contract` | `GET /documents/storage-usage` returns correct schema and numbers | **PASSED** |
| 9 | `test_09_unauthorized_storage_usage_access_rejected` | Unauthenticated requests cannot access storage statistics | **PASSED** |
| 10 | `test_10_missing_s3_production_config_fails_validation` | Production mode fails fast on missing S3 config without leaking secrets | **PASSED** |
| 11 | `test_11_development_mode_supports_local_storage` | Development mode continues to support local storage cleanly | **PASSED** |
| 12 | `test_12_s3_readiness_failure_reported_safely` | S3 readiness probe failure reports degraded health without leaking credentials | **PASSED** |

**Backend Execution Result:**
- `test_storage_governance.py`: **12 passed** in 51.35s.
- Regression suite (`test_storage_abstraction.py`, `test_two_user_storage_isolation.py`, `test_csrf_document_upload.py`, `test_auth_backend.py`, `test_multi_user_security_hardening.py`, `test_storage_governance.py`): **48 passed** in 72.57s.

### 3.2 Frontend Test Suite & Build
- `vitest run`: **12 test suites passed**, **89 tests passed** in 76.34s.
- `tsc -b && vite build`: **Production build succeeded** in 28.43s with zero type errors.

---

## 4. Phase 6B Completion Status

All Phase 6B objectives are fulfilled. Multi-user storage governance, 500 MB per-user pilot quotas, concurrency defenses, S3 production readiness, and the frontend storage meter are operational and verified.

