# Implementation Plan: Multi-User SaaS Foundation

## Overview

Transform the single-user Marathi Scene Text Annotation Platform into a production-grade
multi-tenant SaaS application. The existing OCR, canvas, metrics, and export workflows
are preserved unchanged and integrated into a Project-scoped context. Implementation
proceeds in 13 phases: backend foundation → auth → storage → projects → router refactor
→ analytics → Docker → frontend auth → frontend dashboard → frontend project view →
frontend settings → security hardening → integration tests.

## Tasks

- [x] 1. Backend foundation — config, database, models, Alembic
  - [x] 1.1 Replace config.py with validated env-var settings
    - Rewrite `backend/config.py` using `pydantic-settings` (`BaseSettings`)
    - Required vars: `DATABASE_URL`, `JWT_SECRET`, `NEXTAUTH_SECRET`; call `sys.exit(1)` with descriptive message if any are absent
    - Optional vars: `CORS_ORIGIN`, `IMAGE_STORAGE`, `IMAGES_DIR`, `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`
    - Export a module-level `settings` singleton used everywhere
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 1.2 Rewrite database.py for asyncpg / PostgreSQL
    - Replace `aiosqlite` engine with `create_async_engine("postgresql+asyncpg://...")`
    - Keep `AsyncSession` factory and `get_db` dependency unchanged in signature
    - Remove `init_db()` (Alembic handles schema); keep `Base` declarative base export
    - _Requirements: 6.2, 6.3_

  - [x] 1.3 Rewrite models.py — User, Project, updated Image/Annotation, refresh tokens, analytics tables
    - Add `User` model with UUID PK and all fields from Req 4.1 (id, name, email, password_hash, avatar_url, is_active, analytics_opt_out, role, created_at, updated_at, last_login)
    - Add `Project` model with UUID PK, `user_id` FK → users ON DELETE CASCADE, name CHECK constraint
    - Update `Image`: change `id` to UUID PK, add `project_id` FK → projects ON DELETE CASCADE, add `storage_key`, remove `filepath`
    - Update `Annotation`: change `id` and `image_id` to UUID
    - Add `RefreshToken` model with `token_hash`, `expires_at`
    - Add `AnalyticsEvent`, `OcrAnalytics`, `AnnotationSession` models
    - _Requirements: 1.1, 4.1, 5.1, 6.1, 6.2, 6.5, 16.2_

  - [x] 1.4 Set up Alembic with asyncpg-compatible env.py
    - Run `alembic init backend/alembic`; configure `alembic.ini` to read `DATABASE_URL` from env
    - Edit `backend/alembic/env.py` for async execution (`asyncio.run`) and `target_metadata = Base.metadata`
    - Generate initial migration `0001_initial.py` covering users, projects, images, annotations, refresh_tokens
    - Generate second migration `0002_analytics.py` covering analytics_events, ocr_analytics, annotation_sessions
    - _Requirements: 6.3, 6.4_

  - [ ]* 1.5 Write unit tests for config validation
    - Test that missing `DATABASE_URL`, `JWT_SECRET`, or `NEXTAUTH_SECRET` triggers `sys.exit(1)`
    - Test that all optional vars receive their documented defaults
    - _Requirements: 12.3_

- [x] 2. Auth module — signup, login, refresh, logout, JWT, bcrypt
  - [x] 2.1 Implement auth service (JWT + bcrypt)
    - Create `backend/auth/service.py` with `hash_password`, `verify_password` (bcrypt cost ≥ 12), `create_access_token` (15-min JWT, payload: sub/email/role/exp/iat), `verify_access_token`
    - Implement refresh token helpers: generate opaque UUID, store SHA-256 hash in DB, single-use rotation on each `/auth/refresh` call
    - _Requirements: 1.2, 1.4, 1.5, 14.2, 14.4_

  - [x] 2.2 Implement auth schemas and router
    - Create `backend/auth/schemas.py` (LoginRequest, SignupRequest, TokenResponse)
    - Create `backend/auth/router.py` with POST `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`
    - Set refresh token as HttpOnly, Secure, SameSite=Strict cookie; clear cookie on logout
    - Invalidate refresh token row in DB on logout
    - _Requirements: 1.1, 1.3, 1.4, 1.6_

  - [x] 2.3 Implement get_current_user dependency
    - Create `backend/auth/dependencies.py` with `get_current_user` FastAPI dependency
    - Extract user id from validated JWT; return 401 if token missing/invalid/expired; return 401 if user not found or inactive
    - _Requirements: 3.1, 3.5, 7.1_

  - [ ]* 2.4 Write property test for JWT expiry enforcement (Property 7)
    - **Property 7: JWT expiry enforced**
    - Generate access token with `exp` set to past timestamp; assert any authenticated endpoint returns HTTP 401
    - **Validates: Requirements 3.1, 14.1**

  - [ ]* 2.5 Write property test for password never stored in plaintext (Property 2)
    - **Property 2: Password never stored in plaintext**
    - For arbitrary password strings, assert `users.password_hash != plain_password` after signup
    - **Validates: Requirements 1.2, 14.2**

  - [ ]* 2.6 Write property test for refresh token single-use rotation (Property 3)
    - **Property 3: Refresh token single-use rotation**
    - After using refresh token T once, assert a second POST `/auth/refresh` with T returns HTTP 401
    - **Validates: Requirements 1.5**

  - [ ]* 2.7 Write unit tests for auth service
    - Test `hash_password` / `verify_password` round-trip; test wrong password returns False
    - Test `create_access_token` payload structure; test `verify_access_token` raises on tampered token
    - Test duplicate email signup returns 409
    - _Requirements: 1.2, 1.3, 14.2_

- [x] 3. Storage abstraction — BaseStorageProvider, LocalDiskProvider, factory
  - [x] 3.1 Implement storage interface and LocalDiskProvider
    - Create `backend/storage/base.py` with abstract `BaseStorageProvider` (save, get_url, delete)
    - Create `backend/storage/local.py` with `LocalDiskProvider`: saves to `{IMAGES_DIR}/{project_id}/{filename}`, returns storage_key, serves via `/api/images/file/{storage_key:path}`
    - Create `backend/storage/s3.py` as a stub S3Provider with NotImplementedError
    - Create `backend/storage/factory.py` resolving provider from `IMAGE_STORAGE` env var; expose `get_storage_provider()` as FastAPI dependency
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 3.2 Write unit tests for LocalDiskProvider
    - Test save/get_url/delete round-trip using a tmp directory
    - Test unknown IMAGE_STORAGE value raises ValueError
    - _Requirements: 8.1, 8.2_

- [ ] 4. Project module — CRUD endpoints with ownership checks
  - [x] 4.1 Implement project service and schemas
    - Create `backend/projects/schemas.py` (ProjectCreate, ProjectUpdate, ProjectResponse with image_count and approved_count)
    - Create `backend/projects/service.py` with `get_project_for_user` (returns 403 if user doesn't own project), `list_projects`, `create_project`, `rename_project`, `delete_project`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.1, 7.2_

  - [x] 4.2 Implement project router
    - Create `backend/projects/router.py` with GET `/projects`, POST `/projects`, GET `/projects/{id}`, PATCH `/projects/{id}`, DELETE `/projects/{id}`
    - All routes use `get_current_user` dependency; all write operations call `get_project_for_user` for ownership enforcement
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 7.4_

  - [ ]* 4.3 Write property test for user isolation (Property 1)
    - **Property 1: User isolation — no cross-user data access**
    - Create two users A and B; user A creates a project; assert GET/PATCH/DELETE by user B returns HTTP 403
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 4.4 Write property test for cascade delete completeness (Property 4)
    - **Property 4: Cascade delete completeness**
    - Create project with images and annotations; delete project; assert images and annotations are no longer retrievable via any endpoint
    - **Validates: Requirements 5.4, 6.5**

  - [ ]* 4.5 Write unit tests for project service
    - Test `get_project_for_user` returns 403 for wrong user, 404 for own missing project
    - Test project name length validation (1–100 chars)
    - _Requirements: 5.1, 5.2, 7.2_

- [x] 5. Refactor existing routers under /projects/{id}/
  - [x] 5.1 Refactor images router to project-scoped paths and Storage Service
    - Move `backend/routers/images.py` → `backend/images/router.py`; add `get_current_user` + `get_project_for_user` to all routes
    - Replace `filepath` direct I/O with `storage.save()`, `storage.get_url()`, `storage.delete()` calls
    - Mount all routes under `/projects/{project_id}/images`; add file-serve route `GET /api/images/file/{storage_key:path}`
    - Validate uploaded file MIME type (jpeg/png/webp) and size ≤ 20 MB
    - _Requirements: 8.5, 8.6, 14.5, 15.2_

  - [x] 5.2 Refactor OCR router to project-scoped paths
    - Move `backend/routers/ocr.py` → `backend/ocr/router.py`; add ownership check via `get_project_for_user`
    - Update `image_id` lookups to join through Project to enforce ownership; pass `project_id` to all DB queries
    - Mount routes under `/projects/{project_id}/ocr`; preserve all OCR adapter logic unchanged
    - _Requirements: 7.4, 15.1, 15.2_

  - [x] 5.3 Refactor annotations router to project-scoped paths
    - Move `backend/routers/annotations.py` → `backend/annotations/router.py`; add ownership check via image→project join
    - Mount routes under `/projects/{project_id}/annotations`; preserve all annotation CRUD logic unchanged
    - _Requirements: 7.4, 15.1, 15.2_

  - [x] 5.4 Refactor metrics and export routers to project-scoped paths
    - Move `backend/routers/metrics.py` → `backend/metrics/router.py`; move `backend/routers/export.py` → `backend/export/router.py`
    - Add ownership checks; mount under `/projects/{project_id}/metrics` and `/projects/{project_id}/export`
    - Preserve all metric formulas (AAR, BCR, MAR, TSE) and export serializers (YOLO, COCO, Label Studio, Custom JSON) unchanged
    - _Requirements: 7.4, 15.1, 15.2_

  - [x] 5.5 Update main.py — register all refactored routers, add lifespan Alembic migration step
    - Replace old `routers.*` imports with new module-path imports
    - In lifespan, run `alembic upgrade head` before app starts; remove `init_db()` call
    - Add `RequestSizeLimitMiddleware` (25 MB cap) and update CORS to use `settings.CORS_ORIGIN`
    - _Requirements: 6.4, 12.4, 14.6_

  - [ ]* 5.6 Write unit tests for ownership enforcement on refactored routers
    - Test image upload to another user's project returns 403
    - Test annotation edit on image from another user's project returns 403
    - _Requirements: 7.1, 7.2, 7.4_

- [x] 6. Checkpoint — backend core complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Analytics module — TelemetryService, event recording, session tracking, API endpoints
  - [x] 7.1 Implement analytics schemas and TelemetryService
    - Create `backend/analytics/schemas.py` for all event types listed in Req 16.1 and session fields from Req 16.5–16.6
    - Create `backend/analytics/service.py` with `TelemetryService.record()`: skip if user opted out, insert `AnalyticsEvent` row, fire-and-forget to optional external provider
    - Implement `open_session()` and `close_session()` helpers for `AnnotationSession`
    - Create `backend/analytics/providers/base.py` with abstract `BaseAnalyticsProvider`; create `InternalProvider` default; resolve via `ANALYTICS_PROVIDER` env var
    - _Requirements: 16.1, 16.2, 16.3, 16.5, 16.6, 16.9, 16.10_

  - [x] 7.2 Instrument existing routers with telemetry calls
    - Add `TelemetryService.record()` calls in: auth router (USER_LOGIN, USER_LOGOUT), project router (PROJECT_CREATED, PROJECT_DELETED), images router (IMAGE_UPLOADED, IMAGE_DELETED), OCR router (OCR_STARTED, OCR_COMPLETED, OCR_FAILED), annotations router (ANNOTATION_CREATED, ANNOTATION_EDITED, ANNOTATION_DELETED, ANNOTATION_APPROVED), export router (EXPORT_GENERATED)
    - Add OCR analytics row on OCR_COMPLETED/OCR_FAILED with all fields from Req 16.4
    - _Requirements: 16.1, 16.4_

  - [x] 7.3 Implement analytics API router
    - Create `backend/analytics/router.py` with all 7 endpoints: GET `/analytics/dashboard`, `/analytics/user`, `/analytics/project`, `/analytics/ocr`, `/analytics/events`, `/analytics/productivity`, `/analytics/research`
    - Enforce ownership on non-research endpoints; restrict `/analytics/research` to users with `role = 'researcher'`
    - `/analytics/productivity` uses only closed sessions (end_time IS NOT NULL)
    - `/analytics/research` aggregates from stored events/sessions only — no live cross-table queries
    - _Requirements: 16.7, 16.8, 17.4, 17.5, 18.1, 18.2, 18.3_

  - [ ]* 7.4 Write property test for analytics opt-out (Property 5)
    - **Property 5: Analytics opt-out is honoured**
    - Set `analytics_opt_out = true` for a user; perform actions; assert no `analytics_events` rows with that `user_id` are inserted after opt-out (except final ANALYTICS_DISABLED)
    - **Validates: Requirements 16.9**

  - [ ]* 7.5 Write unit tests for TelemetryService
    - Test opt-out check skips insertion
    - Test `record()` persists correct event_type and user_id
    - Test `open_session` / `close_session` with duration calculation
    - _Requirements: 16.2, 16.3, 16.5, 16.6_

- [x] 8. Security — rate limiting middleware, request size limits, CORS hardening
  - [x] 8.1 Add slowapi rate limiting on auth endpoints
    - Install `slowapi` in `backend/requirements.txt`
    - Attach `Limiter(key_func=get_remote_address)` to the FastAPI app; decorate POST `/auth/login` with `@limiter.limit("5/10minutes")`
    - Return HTTP 429 with `{"detail": "Too many requests, try again later"}` on limit breach; block for 15 min
    - _Requirements: 1.8, 14.3_

  - [x] 8.2 Add RequestSizeLimitMiddleware and finalise CORS configuration
    - Add `RequestSizeLimitMiddleware` capping non-upload requests at 25 MB (return 413)
    - Update CORS middleware to read allowed origins from `settings.CORS_ORIGIN`
    - _Requirements: 12.4, 14.6, 14.8_

  - [ ]* 8.3 Write property test for rate limit enforcement (Property 8)
    - **Property 8: Rate limit enforced**
    - Submit 6 rapid login attempts from the same IP; assert the 6th returns HTTP 429
    - **Validates: Requirements 1.8, 14.3**

  - [ ]* 8.4 Write unit tests for RequestSizeLimitMiddleware
    - Test request body > 25 MB returns 413
    - Test request body ≤ 25 MB passes through
    - _Requirements: 14.6_

- [ ] 9. Docker — Dockerfiles and docker-compose.yml
  - [x] 9.1 Create backend/Dockerfile
    - Python 3.12-slim base; install `requirements.txt`; COPY backend source; entrypoint runs `alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000`
    - Add `/health` GET endpoint to `main.py` returning `{"status": "ok"}`
    - _Requirements: 13.1, 13.4, 13.5_

  - [x] 9.2 Create frontend/Dockerfile
    - Node 20-alpine base; multi-stage build (deps → builder → runner); `next start` as CMD
    - _Requirements: 13.1_

  - [x] 9.3 Create docker-compose.yml and .env.example
    - Define `postgres`, `backend`, `frontend` services per design spec
    - Add named volumes `postgres_data` and `images_data`
    - Add healthchecks for `postgres` (pg_isready) and `backend` (/health); `frontend` depends_on `backend` with `service_healthy`
    - Create `.env.example` documenting all required and optional vars; do NOT commit real secrets
    - _Requirements: 12.1, 12.2, 13.1, 13.2, 13.3, 13.4_

- [x] 10. Checkpoint — backend + Docker complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Frontend auth — NextAuth config, auth pages, SessionProvider
  - [x] 11.1 Migrate frontend to Next.js App Router and install auth dependencies
    - Add `next-auth`, `@auth/core` to `package.json` (exact versions)
    - Convert `src/pages/` to `src/app/` directory structure per design folder layout
    - Create `src/app/layout.tsx` wrapping with `<SessionProvider>` and `<QueryProvider>`
    - Create `src/providers/SessionProvider.tsx` as a `"use client"` wrapper around NextAuth's `SessionProvider`
    - _Requirements: 3.4, 19.6_

  - [x] 11.2 Implement NextAuth configuration and API route
    - Create `src/lib/auth.ts` with `CredentialsProvider` calling `POST /auth/login`; store `accessToken` in JWT callback
    - Create `src/app/api/auth/[...nextauth]/route.ts` exporting NextAuth handlers
    - Configure Google provider conditional on `GOOGLE_CLIENT_ID` env var presence
    - _Requirements: 2.1, 2.4, 3.4_

  - [x] 11.3 Update API client to attach Authorization header and handle 401
    - Rewrite `src/lib/api.ts` typed fetch wrapper: reads `session.accessToken` from `getSession()`; attaches `Authorization: Bearer <token>`; on 401 triggers `signIn()` refresh
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 11.4 Create Login, Signup, and Forgot Password pages
    - `src/app/(auth)/login/page.tsx` — LoginForm with email + password fields, error display, "Sign in with Google" button conditionally rendered
    - `src/app/(auth)/signup/page.tsx` — SignupForm with name, email, password; calls `POST /auth/signup` then auto-login
    - `src/app/(auth)/forgot-password/page.tsx` — placeholder confirmation message, no email sent
    - Add loading state indicators (spinner/skeleton) and user-facing error messages (no raw stack traces)
    - _Requirements: 1.7, 2.1, 19.1, 19.2, 19.3, 19.4, 19.5_

  - [x] 11.5 Create protected route layout guard
    - Create `src/app/dashboard/layout.tsx` and `src/app/projects/[id]/layout.tsx` using `getServerSession`; redirect to `/login?callbackUrl=...` when no session
    - _Requirements: 3.2, 3.3_

  - [ ]* 11.6 Write frontend tests for auth components
    - `LoginForm` — renders fields, shows error message on failed credentials, shows Google button when env var set
    - `SignupForm` — validates required fields, POSTs to correct endpoint
    - `ProtectedLayout` — redirects to `/login` when session is null
    - `api.ts` — attaches Authorization header, calls `signIn` on 401
    - _Requirements: 19.1, 19.2, 19.5_

- [x] 12. Frontend dashboard — Dashboard page, ProjectCard, CreateProjectModal
  - [x] 12.1 Create Dashboard page and ProjectCard component
    - Create `src/app/dashboard/page.tsx` — fetches `GET /projects` via `api.ts`; renders grid of `ProjectCard` components
    - Create `src/components/dashboard/ProjectCard.tsx` — displays name, image count, approved count, `updated_at` as relative timestamp; entire card is a link to `/projects/[id]`
    - Display empty state ("Create your first project") when project list is empty
    - Show loading skeleton while fetching; show error toast on API failure
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 19.4, 19.5_

  - [x] 12.2 Create CreateProjectModal component
    - Create `src/components/dashboard/CreateProjectModal.tsx` — form with required `name` (1–100 chars), optional `description`, optional `default_language` selector
    - On submit calls `POST /projects`; on success closes modal and refreshes project list via React Query invalidation
    - _Requirements: 9.6, 5.1_

  - [ ]* 12.3 Write frontend tests for dashboard components
    - `ProjectCard` — renders name, image/approved counts, relative timestamp, correct href
    - `CreateProjectModal` — validates required name field, calls `POST /projects` on submit, closes on success
    - `DashboardPage` — shows empty state when projects list is empty
    - _Requirements: 9.2, 9.4, 9.6_

- [x] 13. Frontend project view — Project tabs shell, existing annotation UI under Images tab
  - [x] 13.1 Create Project View shell with tabs
    - Create `src/app/projects/[id]/page.tsx` — fetches `GET /projects/{id}`; renders `ProjectHeader` (name, breadcrumb) and `ProjectTabs` (Images, Metrics, Exports, Settings)
    - Create `src/components/projects/ProjectTabs.tsx` — tab navigation component
    - Create `src/components/projects/ProjectHeader.tsx` — project name, breadcrumb back to dashboard
    - _Requirements: 5.7, 10.1_

  - [x] 13.2 Wire existing annotation UI into the Images tab
    - Create `src/app/projects/[id]/images/page.tsx` — renders existing `TopToolbar`, `ImageGallery`, `AnnotationCanvas`, `AnnotationPanel`; pass `projectId` to all API calls via `api.ts`
    - Update `src/lib/api.ts` to scope image/OCR/annotation endpoint paths under `/projects/{projectId}/`
    - Do NOT modify the canvas, panel, toolbar, or gallery component logic
    - _Requirements: 5.8, 10.2, 10.3, 15.1, 15.2, 15.3_

  - [x] 13.3 Create Metrics tab, Exports tab, and Project Settings tab
    - `src/app/projects/[id]/metrics/page.tsx` — renders existing `StatsDashboard` scoped to `project_id`
    - `src/app/projects/[id]/exports/page.tsx` — renders export format picker and download buttons calling scoped export endpoints
    - `src/app/projects/[id]/settings/page.tsx` — Rename Project form, project description, default_language selector, Delete Project button with confirmation dialog
    - _Requirements: 5.7, 10.4, 10.5, 10.6_

  - [ ]* 13.4 Write frontend tests for project view components
    - `ProjectTabs` — renders all 4 tabs, active tab highlights correctly
    - `ProjectHeader` — displays project name, breadcrumb links to `/dashboard`
    - _Requirements: 10.1_

- [ ] 14. Frontend user settings — Profile page and password change
  - [x] 14.1 Create User Settings page
    - Create `src/app/settings/page.tsx` — displays name, email, avatar_url, and "Member Since" (formatted created_at)
    - Provide inline `name` edit form that calls `PATCH /users/me` on save; reflect updated name immediately without re-login
    - Provide Change Password form (current password + new password ≥ 8 chars) calling `POST /users/me/password`; show error on wrong current password
    - Provide Logout button calling NextAuth `signOut()`
    - Display "Delete Account" button as placeholder showing "coming soon" message
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 14.2 Implement users router and service (backend)
    - Create `backend/users/schemas.py` (UserResponse, UpdateNameRequest, ChangePasswordRequest)
    - Create `backend/users/service.py` with `get_user`, `update_name`, `change_password`
    - Create `backend/users/router.py` with GET `/users/me`, PATCH `/users/me`, POST `/users/me/password`
    - Return 400 on wrong current password; never update hash in that case
    - _Requirements: 4.2, 4.3, 4.4, 4.6_

  - [ ]* 14.3 Write unit tests for users service
    - Test `change_password` returns 400 for incorrect current password, updates hash for correct one
    - Test `update_name` persists immediately
    - _Requirements: 4.3, 4.4, 4.6_

- [x] 15. Checkpoint — full frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Integration tests — full lifecycle and cross-user isolation
  - [ ] 16.1 Write full lifecycle integration test
    - Using `pytest` + `httpx.AsyncClient` against an in-process app with a test PostgreSQL DB
    - Flow: POST `/auth/signup` → POST `/auth/login` → POST `/projects` → POST `/projects/{id}/images/upload` → POST `/projects/{id}/ocr/{img_id}` → GET `/projects/{id}/export/{img_id}` → DELETE `/projects/{id}`
    - Assert final state: project gone, images gone, annotations gone (cascade verified)
    - _Requirements: 5.4, 6.5, 15.1_

  - [ ] 16.2 Write cross-user isolation integration test
    - Create users A and B; A creates a project; assert B's GET/PATCH/DELETE on A's project, images, and annotations all return 403
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 16.3 Write token lifecycle integration tests
    - Test expired access token → 401 on any protected endpoint
    - Test refresh token rotation: use T → get new token → use T again → 401
    - Test logout → refresh token gone → `/auth/refresh` returns 401
    - _Requirements: 1.5, 1.6, 3.1, 14.1_

  - [ ] 16.4 Write rate-limiting integration test
    - Submit 6 POST `/auth/login` requests with wrong credentials from same IP; assert 6th returns 429
    - _Requirements: 1.8, 14.3_

- [x] 17. Final checkpoint — all tests pass
  - Ensure all backend and frontend tests pass; verify `docker compose up` starts cleanly; ask the user if questions arise.


## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP delivery
- Each task references specific requirements for full traceability
- Checkpoints at tasks 6, 10, 15, and 17 ensure incremental validation
- Property tests (Properties 1–8) validate correctness invariants from the design document
- The existing OCR adapters, annotation canvas, metric formulas, and export serializers are NEVER modified — only scoped to `project_id`
- All secrets must be supplied via environment variables; `.env.example` documents them all

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5"] },
    { "id": 3, "tasks": ["2.1", "3.1"] },
    { "id": 4, "tasks": ["2.2", "2.3", "3.2", "4.1"] },
    { "id": 5, "tasks": ["2.4", "2.5", "2.6", "2.7", "4.2"] },
    { "id": 6, "tasks": ["4.3", "4.4", "4.5", "5.1"] },
    { "id": 7, "tasks": ["5.2", "5.3", "5.4", "14.2"] },
    { "id": 8, "tasks": ["5.5"] },
    { "id": 9, "tasks": ["5.6", "8.1", "8.2", "7.1"] },
    { "id": 10, "tasks": ["7.2", "8.3", "8.4"] },
    { "id": 11, "tasks": ["7.3", "9.1"] },
    { "id": 12, "tasks": ["7.4", "7.5", "9.2", "9.3"] },
    { "id": 13, "tasks": ["11.1"] },
    { "id": 14, "tasks": ["11.2", "11.3"] },
    { "id": 15, "tasks": ["11.4", "11.5"] },
    { "id": 16, "tasks": ["11.6", "12.1", "14.1", "14.3"] },
    { "id": 17, "tasks": ["12.2"] },
    { "id": 18, "tasks": ["12.3", "13.1"] },
    { "id": 19, "tasks": ["13.2", "13.3"] },
    { "id": 20, "tasks": ["13.4"] },
    { "id": 21, "tasks": ["16.1", "16.2", "16.3", "16.4"] }
  ]
}
```
