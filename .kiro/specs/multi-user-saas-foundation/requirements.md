# Requirements Document

## Introduction

The Multi-User SaaS Foundation transforms the existing single-user Marathi Scene Text Annotation Platform into a production-grade, multi-tenant SaaS application. The existing annotation workflow — OCR auto-annotation, interactive canvas, research metrics, and multi-format export — is preserved exactly as-is and integrated into a Project-scoped context. This feature adds: email+password authentication (with pluggable Google OAuth), a User model, a Project system that replaces the global image list, PostgreSQL with async SQLAlchemy, server-side ownership authorization on every endpoint, an abstract Storage Service for image files, a Project dashboard, per-user settings, privacy-friendly research telemetry, and a one-command Docker Compose deployment.

**Tech Stack (additions/changes):** NextAuth/Auth.js (frontend auth), JWT access + refresh tokens (backend), PostgreSQL + asyncpg (replaces SQLite), Alembic (migrations), Docker Compose.

---

## Glossary

- **Platform**: The Marathi Scene Text Annotation Assistant web application.
- **User**: An authenticated human identity with a unique email address registered on the Platform.
- **Annotator**: A User who reviews, corrects, and approves Annotations.
- **Researcher**: A User who consumes research metrics, analytics, and exported datasets.
- **Project**: A named, User-owned container that groups Images, OCR Runs, Annotations, Metrics, and Exports.
- **Image**: A scene text photograph uploaded to a Project for annotation.
- **Annotation**: A bounding box paired with a text transcription, label category, and confidence score associated with a region in an Image.
- **Bounding_Box**: A rectangle defined by coordinates (x1, y1, x2, y2) that encloses a text region in an Image.
- **OCR_Engine**: An integrated optical character recognition engine (IndicPhotoOCR, EasyOCR, or PaddleOCR) that produces Annotations automatically.
- **Confidence_Score**: A floating-point value in [0.0, 1.0] produced by the OCR_Engine representing its certainty about a predicted text region.
- **Label**: A category tag assigned to an Annotation. Allowed values: `Marathi`, `English`, `Numeric`, `Mixed`, `Logo`.
- **Annotation_Status**: The workflow state of an Image. Allowed values: `Uploaded`, `OCR_Completed`, `Under_Review`, `Approved`.
- **Access_Token**: A short-lived JWT issued to a User upon successful authentication, used to authorize API requests.
- **Refresh_Token**: A long-lived opaque token stored as an HttpOnly cookie, used to obtain a new Access_Token without re-authentication.
- **Password_Hash**: A bcrypt hash of a User's password stored in the database; the plain-text password is never stored.
- **Storage_Service**: A backend abstraction layer that decouples image file I/O from the rest of the application, supporting Local Disk now and cloud providers in the future.
- **Analytics_Event**: A structured, privacy-friendly record of a user action or system event emitted by the Platform for telemetry and research purposes.
- **Annotation_Session**: A contiguous period of annotation activity on a single Image, tracked for productivity and research analytics.
- **Dashboard**: The post-login landing page showing a User's Projects.
- **AAR**: Annotation Acceptance Rate — accepted OCR-generated Annotations / total OCR-generated Annotations for an Image.
- **BCR**: Box Correction Rate — modified OCR-generated Annotations / total OCR-generated Annotations for an Image.
- **MAR**: Manual Addition Rate — manually added Annotations / total final Annotations for an Image.
- **TSE**: Time Saving Estimate — `AAR × 579 seconds`.
- **Export**: The act of serializing Annotations from the Platform into a downloadable file in a specified format.
- **COCO**: Common Objects in Context JSON annotation format.
- **YOLO**: You Only Look Once annotation format using normalised bounding box coordinates.
- **Label_Studio_JSON**: The JSON annotation format compatible with the Label Studio annotation tool.
- **Research_Dashboard**: An administrative view of aggregated, cross-user analytics for research purposes.

---

## Requirements

### Requirement 1: User Registration and Email/Password Authentication

**User Story:** As a visitor, I want to create an account with my email address and password, so that I can access the Platform and keep my work private.

#### Acceptance Criteria

1. WHEN a visitor submits a Sign Up form with a unique email address and a password of at least 8 characters, THE Authentication_Service SHALL create a User record with `id`, `name`, `email`, `password_hash`, `avatar_url`, `created_at`, `updated_at`, `last_login`, and `is_active` fields.
2. THE Authentication_Service SHALL hash all passwords using bcrypt before storing them; THE Authentication_Service SHALL never store or log the plain-text password.
3. IF a Sign Up request is submitted with an email address that already exists in the database, THEN THE Authentication_Service SHALL return an error indicating the email is already registered, without revealing whether the account is active.
4. WHEN a User submits a Login form with valid credentials, THE Authentication_Service SHALL issue a short-lived JWT Access_Token and a long-lived Refresh_Token stored as an HttpOnly, Secure, SameSite=Strict cookie.
5. WHEN a User's Access_Token expires, THE Authentication_Service SHALL accept the Refresh_Token to issue a new Access_Token without requiring the User to re-enter credentials.
6. WHEN a User logs out, THE Authentication_Service SHALL invalidate the Refresh_Token and clear the authentication cookie from the browser.
7. WHEN a User submits a Forgot Password request with a registered email, THE Platform SHALL display a placeholder confirmation page; no password-reset email needs to be sent in this version.
8. THE Platform SHALL display a rate-limiting error after 5 failed login attempts within 10 minutes from the same IP address, blocking further attempts for 15 minutes.

---

### Requirement 2: Google OAuth Authentication (Pluggable Provider)

**User Story:** As a visitor, I want to sign in with my Google account as an alternative to email/password, so that I can authenticate without managing a separate password.

#### Acceptance Criteria

1. WHERE Google OAuth is enabled via environment configuration, THE Authentication_Service SHALL present a "Sign in with Google" option on the Login page.
2. WHEN a User authenticates via Google OAuth and no User record exists for the returned email, THE Authentication_Service SHALL create a new User record with the Google-provided name, email, and avatar URL, and `password_hash` set to `null`.
3. WHEN a User authenticates via Google OAuth and a User record already exists for the returned email, THE Authentication_Service SHALL link the OAuth session to the existing User record and update `last_login`.
4. THE Authentication_Service SHALL be architected so that additional OAuth providers can be added by registering a new NextAuth provider without modifying authentication middleware or business logic.

---

### Requirement 3: JWT Middleware and Protected Routes

**User Story:** As a platform operator, I want all API endpoints and frontend pages to require authentication, so that unauthenticated users cannot access any application data.

#### Acceptance Criteria

1. THE API_Gateway SHALL validate the JWT Access_Token on every API request before forwarding the request to any router; THE API_Gateway SHALL reject requests with missing or invalid tokens with HTTP 401.
2. WHEN a User navigates to any authenticated page without a valid session, THE Frontend SHALL redirect the User to the Login page, preserving the originally requested URL for post-login redirect.
3. WHEN a User successfully logs in, THE Frontend SHALL redirect the User to their Dashboard or the originally requested URL.
4. THE Frontend SHALL persist the User session across browser refreshes using NextAuth session management.
5. THE API_Gateway SHALL extract the authenticated User's `id` from the validated Access_Token and make it available to all downstream route handlers.

---

### Requirement 4: User Model and Profile

**User Story:** As a User, I want to view and update my profile information, so that I can manage my account and identity on the Platform.

#### Acceptance Criteria

1. THE Platform SHALL store the following fields for each User: `id` (UUID), `name`, `email`, `password_hash`, `avatar_url`, `created_at`, `updated_at`, `last_login`, `is_active`.
2. WHEN a User navigates to their Profile page, THE Platform SHALL display the User's `name`, `email`, `avatar_url`, and `created_at` (as "Member Since").
3. WHEN a User submits a Change Password form with a valid current password and a new password of at least 8 characters, THE Authentication_Service SHALL update the `password_hash` and return a success confirmation.
4. IF a User submits a Change Password form with an incorrect current password, THEN THE Authentication_Service SHALL return an error and SHALL NOT update the `password_hash`.
5. THE Platform SHALL display a Delete Account button as a non-functional placeholder in this version; THE Platform SHALL NOT implement account deletion logic.
6. WHEN a User updates their `name`, THE Platform SHALL persist the change immediately and reflect the updated name in the UI without requiring re-login.

---

### Requirement 5: Project System

**User Story:** As an Annotator, I want to organize my Images into named Projects, so that I can manage multiple annotation campaigns independently.

#### Acceptance Criteria

1. WHEN a User creates a Project by providing a `name` (required, 1–100 characters) and optional `description` and `default_language`, THE Project_Service SHALL create a Project record with fields `id`, `user_id`, `name`, `description`, `created_at`, `updated_at`, and `default_language`.
2. THE Project_Service SHALL associate every Project with exactly one User via the `user_id` foreign key; THE Project_Service SHALL reject any attempt to create a Project without an authenticated User identity.
3. WHEN a User renames a Project, THE Project_Service SHALL update the `name` field and the `updated_at` timestamp for that Project.
4. WHEN a User deletes a Project, THE Project_Service SHALL delete the Project record and all associated Images, Annotations, OCR Runs, Metrics, and Exports belonging to that Project.
5. THE Dashboard SHALL display all Projects belonging to the authenticated User as cards showing: `name`, image count, approved image count, and `updated_at`.
6. THE Dashboard SHALL display a "Create Project" button that opens a form to create a new Project.
7. WHEN a User opens a Project, THE Platform SHALL display the Project View with tabs: Images, Metrics, Exports, Settings.
8. THE Images tab in the Project View SHALL contain the existing Upload, Run OCR, Run OCR All, Filters, and Gallery functionality, scoped to the current Project.

---

### Requirement 6: Database Relationships and Scoping

**User Story:** As a platform operator, I want every resource to be owned by a User through a Project, so that the data model enforces multi-tenant isolation at the schema level.

#### Acceptance Criteria

1. THE Database SHALL enforce the following ownership chain: User → Projects → Images → Annotations and OCR Runs; no Image, Annotation, or OCR Run SHALL exist outside a Project.
2. THE Database SHALL use PostgreSQL as the sole database engine; THE Database SHALL use SQLAlchemy 2.0 with the `asyncpg` driver; THE Database SHALL use `postgresql+asyncpg` as the connection URL scheme.
3. THE Migration_Service SHALL use Alembic to manage all database schema changes; no SQLite-specific syntax or `aiosqlite` driver SHALL remain in the codebase.
4. WHEN the application starts, THE Migration_Service SHALL apply any pending Alembic migrations automatically before accepting requests.
5. THE Database SHALL define foreign key constraints with `ON DELETE CASCADE` so that deleting a User cascades to Projects, deleting a Project cascades to Images, and deleting an Image cascades to Annotations and OCR Runs.

---

### Requirement 7: Server-Side Authorization

**User Story:** As a User, I want to be certain that I can never access or modify another User's Projects, Images, or Annotations, so that my annotation data remains private.

#### Acceptance Criteria

1. WHEN a request targets a Project, Image, Annotation, or Export resource, THE Authorization_Service SHALL verify that the resource's owning User `id` matches the authenticated User's `id` from the Access_Token.
2. IF the resource's owner does not match the authenticated User, THEN THE Authorization_Service SHALL return HTTP 403 and SHALL NOT reveal whether the resource exists.
3. THE Authorization_Service SHALL perform ownership verification entirely on the server side; THE Authorization_Service SHALL NOT trust User or Project IDs supplied by the frontend without server-side validation.
4. THE Authorization_Service SHALL enforce ownership checks on all read, write, update, and delete operations for every resource type: Projects, Images, Annotations, OCR Runs, Metrics, and Exports.

---

### Requirement 8: Image Storage Abstraction

**User Story:** As a platform operator, I want image storage to be abstracted behind a service interface, so that the storage backend can be changed from local disk to cloud object storage without modifying application logic.

#### Acceptance Criteria

1. THE Storage_Service SHALL expose the following interface methods: `save(file_data, filename, project_id) → storage_key`, `get_url(storage_key) → str`, `delete(storage_key) → None`.
2. THE Platform SHALL implement a Local Disk provider for the Storage_Service that stores files in a configurable directory on the server filesystem.
3. THE Storage_Service interface SHALL be designed so that AWS S3, Cloudflare R2, GCS, and Azure Blob providers can be added by implementing the same interface without modifying any router, service, or model.
4. THE Platform SHALL select the active Storage_Service provider via the `IMAGE_STORAGE` environment variable; THE Platform SHALL default to the Local Disk provider when `IMAGE_STORAGE` is not set.
5. WHEN the active Storage_Service provider is changed, THE Platform SHALL continue to serve existing image URLs without data loss, assuming the underlying storage is migrated externally.
6. THE rest of the application (routers, annotation service, export service) SHALL interact with images exclusively through the Storage_Service interface and SHALL NOT contain provider-specific storage logic.

---

### Requirement 9: Dashboard

**User Story:** As a User, I want a Dashboard as my landing page after login, so that I can quickly navigate to my Projects and see their status at a glance.

#### Acceptance Criteria

1. WHEN an authenticated User navigates to the root URL (`/`), THE Platform SHALL redirect the User to the Dashboard page (`/dashboard`).
2. THE Dashboard SHALL display one Project card per Project owned by the authenticated User, showing: `name`, image count, approved image count, and `updated_at` formatted as a relative timestamp.
3. THE Dashboard SHALL NOT display a global image list; all image content SHALL be scoped within a Project.
4. WHEN a User has no Projects, THE Dashboard SHALL display an empty state with a prompt to create the first Project.
5. WHEN a User clicks a Project card, THE Platform SHALL navigate to the Project View for that Project.
6. WHEN a User clicks "Create Project", THE Platform SHALL display a modal or form to enter Project `name`, optional `description`, and optional `default_language`, and submit to create the Project.

---

### Requirement 10: Project View and Existing Workflow Integration

**User Story:** As an Annotator, I want to access all annotation tools within a Project View, so that my workflow is organized per Project and the existing canvas, OCR, and export tools work exactly as before.

#### Acceptance Criteria

1. THE Project_View SHALL display the Project name and tabs: Images, Metrics, Exports, Settings.
2. THE Images tab SHALL contain the full existing annotation workflow: image upload, Run OCR (single), Run OCR All (batch), confidence filters, image gallery, annotation canvas, and annotation panel.
3. THE Platform SHALL NOT modify the OCR logic, annotation canvas, metrics computation, export serializers, batch OCR, or workflow state machine; THE Platform SHALL integrate these components into the Project context by passing `project_id` to all scoped API calls.
4. THE Metrics tab SHALL display per-image and project-level AAR, BCR, MAR, and TSE metrics scoped to the current Project.
5. THE Exports tab SHALL expose all existing export formats (YOLO, COCO, Label Studio JSON, Custom JSON) scoped to the current Project.
6. THE Settings tab SHALL display the Project `name`, `description`, `default_language`, and `created_at`, and provide a "Rename Project" action and a "Delete Project" action with a confirmation step.

---

### Requirement 11: User Settings Page

**User Story:** As a User, I want a settings page where I can manage my account, so that I can update my profile and control my account lifecycle.

#### Acceptance Criteria

1. WHEN a User navigates to the Settings page, THE Platform SHALL display: `name`, `email`, `avatar_url`, and `created_at` (as "Member Since").
2. THE Settings page SHALL provide a Change Password form requiring the current password and a new password of at least 8 characters.
3. THE Settings page SHALL provide a "Logout" button that triggers the logout flow described in Requirement 1.6.
4. THE Settings page SHALL display a "Delete Account" button as a placeholder; clicking it SHALL display a message that this feature is coming soon, without performing any account deletion.
5. WHEN a User saves an updated `name` from the Settings page, THE Platform SHALL persist the change and update the displayed name immediately.

---

### Requirement 12: Deployment Configuration and Secrets Management

**User Story:** As a platform operator, I want all secrets and environment-specific settings to be supplied via environment variables, so that the application can be deployed without hardcoded credentials.

#### Acceptance Criteria

1. THE Platform SHALL read the following configuration values exclusively from environment variables: `DATABASE_URL`, `JWT_SECRET`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `API_BASE_URL`, `IMAGE_STORAGE`, `CORS_ORIGIN`.
2. THE Platform SHALL NOT contain any hardcoded secrets, API keys, database passwords, or JWT signing keys in source code or committed configuration files.
3. IF a required environment variable (`DATABASE_URL`, `JWT_SECRET`, `NEXTAUTH_SECRET`) is missing at startup, THEN THE Platform SHALL log a descriptive error message identifying the missing variable and exit without starting.
4. THE Platform SHALL use `CORS_ORIGIN` to configure allowed origins for CORS; THE Platform SHALL reject cross-origin requests from origins not listed in `CORS_ORIGIN`.

---

### Requirement 13: Docker Compose Deployment

**User Story:** As a platform operator, I want to start the entire application stack with a single command, so that deployment and onboarding are simple and reproducible.

#### Acceptance Criteria

1. THE Repository SHALL include a `docker-compose.yml` file defining the following services: `frontend` (Next.js), `backend` (FastAPI), and `postgres` (PostgreSQL).
2. THE `docker-compose.yml` SHALL define a named persistent volume for PostgreSQL data and a named persistent volume for uploaded image files, so that data survives container restarts.
3. WHEN `docker compose up` is executed from the repository root, THE Platform SHALL become accessible with a functional UI and API within 60 seconds, assuming all environment variables are provided via a `.env` file.
4. THE `docker-compose.yml` SHALL define health checks for the `backend` and `postgres` services; THE `frontend` service SHALL not start until the `backend` health check passes.
5. THE `backend` service SHALL run Alembic migrations automatically on container startup before accepting HTTP requests.

---

### Requirement 14: Security

**User Story:** As a User, I want the Platform to be secured against common web vulnerabilities, so that my account and data are protected.

#### Acceptance Criteria

1. THE API_Gateway SHALL validate the JWT signature and expiry on every authenticated request; THE API_Gateway SHALL return HTTP 401 for tokens with invalid signatures or that have expired.
2. THE Authentication_Service SHALL hash all passwords using bcrypt with a cost factor of at least 12 before storing them.
3. THE Platform SHALL enforce rate limiting of 5 login attempts per IP address per 10-minute window; IF the limit is exceeded, THEN THE Platform SHALL return HTTP 429 and block further attempts from that IP for 15 minutes.
4. THE Platform SHALL store Refresh_Tokens in HttpOnly, Secure, SameSite=Strict cookies; THE Platform SHALL NOT expose Refresh_Tokens to JavaScript.
5. THE Platform SHALL validate all file uploads: accepted MIME types are `image/jpeg`, `image/png`, and `image/webp`; maximum file size is 20 MB; only authenticated Users may upload files.
6. THE Platform SHALL enforce a maximum request body size of 25 MB for all non-file-upload endpoints.
7. THE Frontend SHALL send the CSRF token on all state-changing requests; THE API_Gateway SHALL reject state-changing requests missing a valid CSRF token.
8. THE Platform SHALL configure CORS to allow requests only from the origin specified in `CORS_ORIGIN`.

---

### Requirement 15: Preserve Existing Annotation Features

**User Story:** As an Annotator, I want all existing annotation tools to continue working exactly as before, so that the SaaS migration does not disrupt my annotation workflow.

#### Acceptance Criteria

1. THE Platform SHALL preserve without modification the following modules: OCR adapter logic (IndicPhotoOCR, EasyOCR, PaddleOCR adapters), annotation canvas interactions (draw, move, resize, delete, zoom, pan), metrics formulas (AAR, BCR, MAR, TSE), export serializers (YOLO, COCO, Label Studio JSON, Custom JSON), batch OCR queue, and workflow state machine (`Uploaded → OCR_Completed → Under_Review → Approved`).
2. THE Platform SHALL integrate the existing modules into the Project context by adding `project_id` as a scoping parameter to all database queries and API endpoints that currently operate on a global scope.
3. WHEN an Annotator performs any existing annotation action within a Project, THE Platform SHALL behave identically to the current single-user platform with respect to canvas rendering, OCR triggering, status transitions, and export output.

---

### Requirement 16: Analytics and Research Telemetry

**User Story:** As a researcher, I want the Platform to record privacy-friendly usage events and annotation session data, so that I can analyze annotation efficiency and platform usage patterns.

#### Acceptance Criteria

1. THE Telemetry_Service SHALL record the following Analytics_Events: `USER_LOGIN`, `USER_LOGOUT`, `PROJECT_CREATED`, `PROJECT_DELETED`, `IMAGE_UPLOADED`, `IMAGE_DELETED`, `OCR_STARTED`, `OCR_COMPLETED`, `OCR_FAILED`, `ANNOTATION_CREATED`, `ANNOTATION_EDITED`, `ANNOTATION_DELETED`, `ANNOTATION_APPROVED`, `EXPORT_GENERATED`, `DATASET_DOWNLOADED`.
2. THE Telemetry_Service SHALL record the following fields for every Analytics_Event: `event_id`, `event_type`, `user_id`, `project_id`, `image_id`, `ocr_engine`, `model_version`, `timestamp`, `duration_ms`, `metadata` (JSON).
3. THE Telemetry_Service SHALL never record passwords, image pixel data, annotation text content, or any other personally identifiable information in Analytics_Event records.
4. THE Telemetry_Service SHALL record the following additional fields for `OCR_COMPLETED` and `OCR_FAILED` events: `processing_time`, `number_of_boxes`, `average_confidence`, `accepted_boxes`, `rejected_boxes`, `corrected_boxes`, `manual_boxes`, `difficulty_score`, `failure_reason`, image `width`, image `height`, image `orientation`, and `language`.
5. WHEN an Annotator begins editing an Image, THE Telemetry_Service SHALL open an Annotation_Session record with fields: `session_id`, `user_id`, `project_id`, `image_id`, `start_time`.
6. WHEN an Annotator closes or navigates away from an Image editor, THE Telemetry_Service SHALL close the Annotation_Session record with: `end_time`, `duration`, `annotations_created`, `annotations_corrected`, `annotations_deleted`, `zoom_operations`, `pan_operations`, `ocr_used`.
7. THE Analytics_API SHALL expose the following read-only endpoints: `GET /analytics/project`, `GET /analytics/user`, `GET /analytics/ocr`, `GET /analytics/dashboard`, `GET /analytics/events`, `GET /analytics/productivity`, `GET /analytics/research`.
8. THE Analytics_API endpoints SHALL enforce the same ownership authorization as all other endpoints; a User SHALL only access analytics for their own Projects and Images via the non-research endpoints.
9. WHEN a User disables analytics in their account settings, THE Telemetry_Service SHALL stop recording Analytics_Events for that User and SHALL record a final `ANALYTICS_DISABLED` event before ceasing further recording.
10. THE Telemetry_Service SHALL be implemented with a pluggable provider interface so that Mixpanel, PostHog, Google Analytics, Plausible, or OpenTelemetry can be configured as the analytics backend without modifying any router or business logic.

---

### Requirement 17: Research Dashboard

**User Story:** As a researcher, I want an aggregated view of platform-wide annotation activity, so that I can track dataset creation progress and annotator productivity.

#### Acceptance Criteria

1. THE Research_Dashboard SHALL display the following aggregate statistics: total Users, total Projects, total Images, total Annotations, total Approved Images, average annotation time per Image, average OCR confidence, and average OCR acceptance rate.
2. THE Research_Dashboard SHALL display the following ranked lists: most difficult Images (by difficulty_score), most common OCR failure reasons, OCR engine usage distribution, and export format distribution.
3. THE Research_Dashboard SHALL display user activity for the last 30 days, a list of top annotators by approved image count, and a recent activity feed.
4. THE Analytics_API `GET /analytics/research` endpoint SHALL aggregate data across all Users and Projects; access to this endpoint SHALL be restricted to Users with the `researcher` role or equivalent elevated privilege.
5. WHEN the `GET /analytics/research` endpoint is called, THE Analytics_API SHALL return results computed from stored Analytics_Events and Annotation_Sessions and SHALL NOT perform live queries across all annotation tables.

---

### Requirement 18: User Productivity Metrics

**User Story:** As a researcher, I want per-user productivity statistics derived from Annotation_Session data, so that I can understand annotation efficiency across the team.

#### Acceptance Criteria

1. THE Analytics_API `GET /analytics/productivity` endpoint SHALL return the following per-User statistics computed from Annotation_Session records: average annotation time per Image, Images annotated per hour, bounding boxes annotated per minute, correction percentage, OCR acceptance percentage, manual addition percentage, and export frequency.
2. WHEN computing productivity metrics, THE Analytics_API SHALL use only closed Annotation_Sessions (those with a recorded `end_time`).
3. THE Analytics_API SHALL return productivity metrics only for the authenticated User's own sessions via the standard `/analytics/productivity` endpoint; cross-user productivity data SHALL be accessible only through the research endpoint.

---

### Requirement 19: Frontend User Experience

**User Story:** As a User, I want a polished, responsive authentication and navigation experience, so that the SaaS Platform feels professional and easy to use.

#### Acceptance Criteria

1. THE Platform SHALL display a Login page with fields for email, password, and a submit button; WHERE Google OAuth is enabled, THE Platform SHALL also display a "Sign in with Google" button.
2. THE Platform SHALL display a Sign Up page with fields for name, email, password, and a submit button.
3. THE Platform SHALL display a Forgot Password placeholder page that shows a confirmation message when submitted, without sending any email.
4. WHEN the Platform is loading data from the API, THE Frontend SHALL display a loading state indicator to communicate to the User that an action is in progress.
5. WHEN an API request fails, THE Frontend SHALL display a descriptive error message to the User; THE Frontend SHALL NOT display raw stack traces or internal error codes.
6. THE Frontend SHALL use a responsive layout that is functional on screen widths from 768 px upward.
