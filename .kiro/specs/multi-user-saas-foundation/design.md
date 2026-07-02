# Design Document — Multi-User SaaS Foundation

## Overview

This document describes the technical design for transforming the Marathi Scene Text Annotation Platform from a single-user local tool into a production-grade multi-tenant SaaS application. The existing annotation workflow (OCR, canvas, metrics, export) is preserved unchanged and integrated into a Project-scoped context.

**Key design decisions:**
- **JWT authentication** — short-lived access tokens (15 min) + long-lived refresh tokens (7 days) in HttpOnly cookies. `python-jose` for signing, `passlib[bcrypt]` for password hashing.
- **NextAuth/Auth.js** — frontend session management with credentials provider (email+password) and pluggable OAuth providers.
- **PostgreSQL + asyncpg** — replaces SQLite; UUID primary keys; cascade deletes enforce ownership chain at the schema level.
- **Alembic** — database migration management; applied automatically on container startup.
- **Storage Service** — abstract interface with `LocalDiskProvider` now; S3/GCS/R2 added by implementing the same interface.
- **Analytics** — internal PostgreSQL tables for events, OCR analytics, and annotation sessions; pluggable external provider interface for Mixpanel/PostHog/OpenTelemetry.
- **Docker Compose** — frontend + backend + postgres, one-command startup.

---

## Architecture

```
Browser
  ├── /login, /signup, /forgot-password  (unauthenticated)
  ├── /dashboard                          (protected)
  ├── /projects/[id]                      (protected)
  └── /settings                           (protected)
        ↕ NextAuth session (JWT cookie)
Frontend (Next.js 14 App Router)
        ↕ HTTP + Bearer token
Backend (FastAPI)
  ├── auth/          JWT middleware, login, signup, refresh, logout
  ├── users/         User CRUD, profile, password change
  ├── projects/      Project CRUD, ownership checks
  ├── images/        Image upload, serve, delete (via Storage Service)
  ├── annotations/   Annotation CRUD (unchanged logic)
  ├── ocr/           OCR trigger, batch OCR (unchanged logic)
  ├── metrics/       AAR/BCR/MAR/TSE (unchanged logic)
  ├── export/        YOLO/COCO/LS/JSON (unchanged logic)
  ├── analytics/     Events, sessions, productivity, research
  └── storage/       LocalDiskProvider | S3Provider (interface)
        ↕ asyncpg
PostgreSQL
  ├── users
  ├── projects
  ├── images
  ├── annotations
  ├── analytics_events
  ├── ocr_analytics
  └── annotation_sessions
```

---

## Folder Structure

```
backend/
  auth/
    router.py          # /auth/login, /auth/signup, /auth/refresh, /auth/logout
    service.py         # JWT creation, bcrypt hashing, token validation
    dependencies.py    # get_current_user FastAPI dependency
    schemas.py         # LoginRequest, SignupRequest, TokenResponse
  users/
    router.py          # /users/me, PATCH /users/me, POST /users/me/password
    service.py
    schemas.py
  projects/
    router.py          # CRUD /projects
    service.py
    schemas.py
  images/
    router.py          # upload, list, delete, serve (project-scoped)
    service.py
  annotations/
    router.py          # unchanged routes, now project-scoped
    service.py         # unchanged logic
  ocr/
    router.py          # unchanged, now project-scoped
    service.py         # unchanged
    base.py, indic_photo_ocr.py  # unchanged adapters
  metrics/
    router.py          # unchanged, project-scoped
    service.py         # unchanged formulas
  export/
    router.py          # unchanged serializers, project-scoped
    service.py
  storage/
    base.py            # BaseStorageProvider interface
    local.py           # LocalDiskProvider
    s3.py              # S3Provider stub
    factory.py         # resolve provider from IMAGE_STORAGE env var
  analytics/
    router.py          # /analytics/* endpoints
    service.py         # event recording, session tracking
    schemas.py
  models.py            # all ORM models (User, Project, Image, Annotation, ...)
  database.py          # async engine, session factory (asyncpg)
  config.py            # env vars with startup validation
  main.py              # app factory, router registration, lifespan

frontend/
  src/
    app/
      (auth)/
        login/page.tsx
        signup/page.tsx
        forgot-password/page.tsx
      dashboard/page.tsx
      projects/
        [id]/
          page.tsx           # Project View shell with tabs
          images/page.tsx    # existing annotation UI
          metrics/page.tsx
          exports/page.tsx
          settings/page.tsx
      settings/page.tsx      # User profile
      layout.tsx             # root layout with auth check
    components/
      auth/                  # LoginForm, SignupForm
      dashboard/             # ProjectCard, CreateProjectModal
      projects/              # ProjectTabs, ProjectHeader
      annotation/            # existing canvas, gallery, panel, toolbar (unchanged)
    lib/
      auth.ts                # NextAuth config
      api.ts                 # typed fetch client (adds Authorization header)
    providers/
      QueryProvider.tsx      # React Query (unchanged)
      SessionProvider.tsx    # NextAuth SessionProvider wrapper
```

---

## Data Models

### PostgreSQL Schema

```sql
-- Users
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT,                    -- NULL for OAuth-only accounts
    avatar_url    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    analytics_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
    role          TEXT NOT NULL DEFAULT 'annotator', -- 'annotator' | 'researcher'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login    TIMESTAMPTZ
);

-- Projects
CREATE TABLE projects (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name             TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    description      TEXT,
    default_language TEXT NOT NULL DEFAULT 'Marathi',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Images (adds project_id, storage_key; removes filepath)
CREATE TABLE images (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    storage_key  TEXT NOT NULL,   -- opaque key used by Storage Service
    width        INTEGER NOT NULL,
    height       INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Uploaded',
    upload_date  TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at  TIMESTAMPTZ
);

-- Annotations (unchanged columns, id becomes UUID, image_id references new images)
CREATE TABLE annotations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id      UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    x1 REAL NOT NULL, y1 REAL NOT NULL, x2 REAL NOT NULL, y2 REAL NOT NULL,
    text          TEXT NOT NULL DEFAULT '',
    label         TEXT NOT NULL DEFAULT 'Marathi',
    confidence    REAL NOT NULL DEFAULT 1.0,
    accepted      BOOLEAN NOT NULL DEFAULT FALSE,
    ocr_generated BOOLEAN NOT NULL DEFAULT FALSE,
    is_corrected  BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Refresh tokens (for invalidation on logout)
CREATE TABLE refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Analytics events
CREATE TABLE analytics_events (
    event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type    TEXT NOT NULL,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    project_id    UUID REFERENCES projects(id) ON DELETE SET NULL,
    image_id      UUID REFERENCES images(id) ON DELETE SET NULL,
    ocr_engine    TEXT,
    model_version TEXT,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms   INTEGER,
    metadata      JSONB
);

-- OCR analytics (one row per OCR run)
CREATE TABLE ocr_analytics (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id         UUID REFERENCES analytics_events(event_id) ON DELETE CASCADE,
    image_id         UUID REFERENCES images(id) ON DELETE SET NULL,
    processing_time  REAL,
    number_of_boxes  INTEGER,
    average_confidence REAL,
    accepted_boxes   INTEGER,
    rejected_boxes   INTEGER,
    corrected_boxes  INTEGER,
    manual_boxes     INTEGER,
    difficulty_score REAL,
    failure_reason   TEXT,
    image_width      INTEGER,
    image_height     INTEGER,
    orientation      TEXT,
    language         TEXT
);

-- Annotation sessions
CREATE TABLE annotation_sessions (
    session_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id            UUID REFERENCES projects(id) ON DELETE SET NULL,
    image_id              UUID REFERENCES images(id) ON DELETE SET NULL,
    start_time            TIMESTAMPTZ NOT NULL,
    end_time              TIMESTAMPTZ,
    duration              INTEGER,          -- seconds
    annotations_created   INTEGER DEFAULT 0,
    annotations_corrected INTEGER DEFAULT 0,
    annotations_deleted   INTEGER DEFAULT 0,
    zoom_operations       INTEGER DEFAULT 0,
    pan_operations        INTEGER DEFAULT 0,
    ocr_used              BOOLEAN DEFAULT FALSE
);
```

---

## Authentication Design

### Token Flow

```
POST /auth/signup  →  create user, return access_token + set refresh cookie
POST /auth/login   →  verify bcrypt, return access_token + set refresh cookie
POST /auth/refresh →  validate refresh token from cookie, return new access_token
POST /auth/logout  →  delete refresh token from DB, clear cookie
```

### JWT Structure

```python
# Access token payload (15 min TTL)
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "annotator",          # or "researcher"
  "exp": <timestamp>,
  "iat": <timestamp>
}

# Refresh token: opaque UUID, stored as SHA-256 hash in refresh_tokens table
```

### FastAPI Dependency

```python
# backend/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

async def get_current_user(
    token: str = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = verify_access_token(token.credentials)  # raises 401 if invalid
    user = await get_user_by_id(payload["sub"], db)
    if not user or not user.is_active:
        raise HTTPException(status_code=401)
    return user
```

### NextAuth Configuration (Frontend)

```typescript
// frontend/src/lib/auth.ts
export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      async authorize(credentials) {
        const res = await fetch(`${API_BASE}/auth/login`, { ... });
        if (!res.ok) return null;
        return res.json();  // { id, name, email, accessToken }
      }
    }),
    // GoogleProvider goes here when GOOGLE_CLIENT_ID env var is set
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) token.accessToken = user.accessToken;
      return token;
    },
    session({ session, token }) {
      session.accessToken = token.accessToken;
      return session;
    }
  }
};
```

---

## Authorization Design

Every router that accesses a Project, Image, Annotation, or Export resource uses a shared ownership helper:

```python
# backend/projects/service.py
async def get_project_for_user(
    project_id: UUID,
    user: User,
    db: AsyncSession,
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user.id   # ownership enforced here
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=403, detail="Not found")  # 403 not 404
    return project
```

Image and Annotation ownership is verified by joining through Project:

```python
# Verify image belongs to user's project
image = await db.execute(
    select(Image)
    .join(Project, Image.project_id == Project.id)
    .where(Image.id == image_id, Project.user_id == user.id)
)
```

---

## Storage Service Design

```python
# backend/storage/base.py
from abc import ABC, abstractmethod

class BaseStorageProvider(ABC):
    @abstractmethod
    async def save(self, data: bytes, filename: str, project_id: str) -> str:
        """Save file and return opaque storage_key."""

    @abstractmethod
    def get_url(self, storage_key: str) -> str:
        """Return a URL to serve the file."""

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Delete the file."""

# backend/storage/local.py
class LocalDiskProvider(BaseStorageProvider):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    async def save(self, data: bytes, filename: str, project_id: str) -> str:
        dest = self.base_dir / project_id / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"{project_id}/{filename}"   # storage_key

    def get_url(self, storage_key: str) -> str:
        return f"/api/images/file/{storage_key}"

    async def delete(self, storage_key: str) -> None:
        (self.base_dir / storage_key).unlink(missing_ok=True)

# backend/storage/factory.py
def get_storage_provider() -> BaseStorageProvider:
    provider = os.getenv("IMAGE_STORAGE", "local")
    if provider == "local":
        return LocalDiskProvider(Path(os.getenv("IMAGES_DIR", "backend/images")))
    elif provider == "s3":
        from backend.storage.s3 import S3Provider
        return S3Provider(...)
    raise ValueError(f"Unknown IMAGE_STORAGE provider: {provider}")

storage = get_storage_provider()  # singleton, injected via FastAPI dependency
```

---

## Analytics Service Design

```python
# backend/analytics/service.py
class TelemetryService:
    """
    Records analytics events to the internal PostgreSQL tables.
    Dispatches to an optional external provider (Mixpanel, PostHog, etc.)
    if configured via ANALYTICS_PROVIDER env var.
    """

    async def record(self, event_type: str, user_id: UUID | None,
                     project_id: UUID | None = None,
                     image_id: UUID | None = None,
                     duration_ms: int | None = None,
                     metadata: dict | None = None,
                     db: AsyncSession = None) -> None:
        # Skip if user has opted out
        if user_id and await self._is_opted_out(user_id, db):
            return
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            project_id=project_id,
            image_id=image_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        db.add(event)
        await db.flush()
        # Dispatch to external provider (fire-and-forget)
        if self._external_provider:
            asyncio.create_task(
                self._external_provider.track(event_type, user_id, metadata)
            )
```

### Pluggable External Provider Interface

```python
# backend/analytics/providers/base.py
class BaseAnalyticsProvider(ABC):
    @abstractmethod
    async def track(self, event_type: str, user_id: str, properties: dict) -> None: ...

# Resolved via ANALYTICS_PROVIDER env var:
# "internal" (default) → only PostgreSQL tables
# "posthog"            → PostHogProvider
# "mixpanel"           → MixpanelProvider
# "opentelemetry"      → OpenTelemetryProvider
```

---

## API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Register new user |
| `POST` | `/auth/login` | Login, returns access token |
| `POST` | `/auth/refresh` | Refresh access token via cookie |
| `POST` | `/auth/logout` | Invalidate refresh token |

### Users
| Method | Path | Description |
|---|---|---|
| `GET` | `/users/me` | Get current user profile |
| `PATCH` | `/users/me` | Update name / avatar |
| `POST` | `/users/me/password` | Change password |

### Projects
| Method | Path | Description |
|---|---|---|
| `GET` | `/projects` | List user's projects |
| `POST` | `/projects` | Create project |
| `GET` | `/projects/{id}` | Get project details + counts |
| `PATCH` | `/projects/{id}` | Rename project |
| `DELETE` | `/projects/{id}` | Delete project + all contents |

### Images (project-scoped)
| Method | Path | Description |
|---|---|---|
| `POST` | `/projects/{id}/images/upload` | Upload images |
| `GET` | `/projects/{id}/images` | List images |
| `GET` | `/projects/{id}/images/pending-ocr` | List Uploaded images |
| `GET` | `/projects/{id}/images/{img_id}` | Get image metadata |
| `DELETE` | `/projects/{id}/images/{img_id}` | Delete image |
| `PATCH` | `/projects/{id}/images/{img_id}/status` | Update status |
| `GET` | `/api/images/file/{storage_key:path}` | Serve image file |

### OCR, Annotations, Metrics, Export
All existing endpoints remain unchanged in logic; routes move under `/projects/{id}/`:
- `POST /projects/{id}/ocr/{img_id}`
- `POST /projects/{id}/ocr/batch/all`
- `GET/POST/PATCH/DELETE /projects/{id}/annotations/{img_id}`
- `GET /projects/{id}/metrics/{img_id}`
- `GET /projects/{id}/metrics/project`
- `GET /projects/{id}/export/{img_id}`
- `GET /projects/{id}/export/all`

### Analytics
| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/dashboard` | Summary stats for current user |
| `GET` | `/analytics/user` | Per-user event history |
| `GET` | `/analytics/project?project_id=` | Per-project analytics |
| `GET` | `/analytics/ocr` | OCR analytics |
| `GET` | `/analytics/events` | Raw event list |
| `GET` | `/analytics/productivity` | User productivity metrics |
| `GET` | `/analytics/research` | Cross-user research dashboard (researcher role) |

---

## Docker Compose Design

```yaml
# docker-compose.yml
version: "3.9"
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: annotation
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/annotation
      JWT_SECRET: ${JWT_SECRET}
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      CORS_ORIGIN: ${NEXTAUTH_URL}
      IMAGE_STORAGE: local
      IMAGES_DIR: /app/images
    volumes:
      - images_data:/app/images
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      retries: 5

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: ${NEXTAUTH_URL}
      NEXT_PUBLIC_API_BASE_URL: ${API_BASE_URL}
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "3000:3000"

volumes:
  postgres_data:
  images_data:
```

---

## Security Design

### Rate Limiting

```python
# backend/auth/router.py — using slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/10minutes")
async def login(request: Request, ...):
    ...
```

Failed attempts are tracked in Redis (or in-memory for single-instance deployments). After 5 failures from the same IP within 10 minutes, subsequent requests return HTTP 429 for 15 minutes.

### Password Hashing

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### Refresh Token Storage

Refresh tokens are never stored in plaintext. On issue:
1. Generate a random UUID as the token value
2. Store `SHA-256(token)` in `refresh_tokens.token_hash`
3. Return the raw token to the frontend in an HttpOnly cookie

On validation:
1. Read token from cookie
2. Compute `SHA-256(token)` and look up in DB
3. Check `expires_at > now()`
4. Delete the token row (single-use rotation — issue new refresh token on each refresh)

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGIN", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Request Size Limits

```python
# backend/main.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 25 * 1024 * 1024:
            return Response("Request too large", status_code=413)
        return await call_next(request)
```

---

## Frontend Component Design

### Auth Pages

```
/login
  └── LoginForm
        ├── email input
        ├── password input
        ├── Submit → signIn("credentials", ...)
        └── Google button (if GOOGLE_CLIENT_ID set)

/signup
  └── SignupForm
        ├── name, email, password inputs
        └── Submit → POST /auth/signup → auto-login

/forgot-password
  └── ForgotPasswordForm
        └── Submit → show placeholder confirmation (no email sent)
```

### Dashboard

```
/dashboard
  └── DashboardPage
        ├── Navbar (logo, user avatar, settings link, logout)
        ├── CreateProjectButton → CreateProjectModal
        │     ├── name (required), description, default_language
        │     └── Submit → POST /projects
        └── ProjectGrid
              └── ProjectCard × N
                    ├── name
                    ├── image count / approved count
                    ├── last updated (relative)
                    └── onClick → /projects/[id]
```

### Project View

```
/projects/[id]
  └── ProjectLayout
        ├── ProjectHeader (name, breadcrumb, settings icon)
        ├── ProjectTabs: Images | Metrics | Exports | Settings
        │
        ├── [Images tab]  ← existing annotation UI, project-scoped
        │     ├── TopToolbar (unchanged)
        │     ├── ImageGallery (project-scoped fetch)
        │     ├── AnnotationCanvas (unchanged)
        │     └── AnnotationPanel (unchanged)
        │
        ├── [Metrics tab]
        │     └── StatsDashboard (project-scoped)
        │
        ├── [Exports tab]
        │     └── ExportPanel (format picker, download buttons)
        │
        └── [Settings tab]
              ├── ProjectNameForm (rename)
              ├── ProjectDescription
              ├── DefaultLanguage selector
              └── DeleteProjectButton (with confirmation)
```

### Session Provider Integration

```typescript
// frontend/src/app/layout.tsx
import { SessionProvider } from 'next-auth/react';
import { QueryProvider } from '@/providers/QueryProvider';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <SessionProvider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
```

### Protected Route Guard

```typescript
// frontend/src/app/dashboard/layout.tsx
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';

export default async function ProtectedLayout({ children }) {
  const session = await getServerSession(authOptions);
  if (!session) redirect('/login');
  return <>{children}</>;
}
```

### API Client with Auth Header

```typescript
// frontend/src/lib/api.ts
import { getSession } from 'next-auth/react';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = await getSession();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': session?.accessToken ? `Bearer ${session.accessToken}` : '',
      ...init?.headers,
    },
    ...init,
  });
  if (res.status === 401) {
    // Token expired — trigger NextAuth refresh
    await signIn();
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}
```

---

## Alembic Migration Design

```
backend/
  alembic/
    env.py          # asyncpg-compatible env setup
    versions/
      0001_initial.py    # users, projects, images, annotations, refresh_tokens
      0002_analytics.py  # analytics_events, ocr_analytics, annotation_sessions
  alembic.ini
```

The `env.py` imports all models from `backend/models.py` using `target_metadata = Base.metadata` and runs migrations in async mode via `asyncio.run()`.

On container startup, `backend/Dockerfile` runs:
```bash
alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## Correctness Properties

### Property 1: User isolation — no cross-user data access
For any two users A and B and any resource R owned by B, any API request by A targeting R must return HTTP 403, regardless of whether A knows R's ID.

**Validates: Requirements 7.1, 7.2, 7.3**

### Property 2: Password never stored in plaintext
For any signup or password-change operation, the value stored in `users.password_hash` must not equal the submitted plain-text password.

**Validates: Requirements 1.2, 14.2**

### Property 3: Refresh token single-use rotation
For any refresh token T, after T is used to obtain a new access token, a second use of T must return HTTP 401.

**Validates: Requirements 1.5**

### Property 4: Cascade delete completeness
For any Project P deleted by its owner, all Images, Annotations, and OCR runs belonging to P must no longer be retrievable via any API endpoint after deletion.

**Validates: Requirements 5.4, 6.5**

### Property 5: Analytics opt-out is honoured
For any User U with `analytics_opt_out = true`, no `analytics_events` row with `user_id = U.id` must be inserted after the opt-out is recorded (except the final `ANALYTICS_DISABLED` event).

**Validates: Requirements 16.9**

### Property 6: Storage key independence
For any annotation action (create, update, delete), the Storage_Service provider can be swapped without changing any annotation service, router, or model code.

**Validates: Requirements 8.3, 8.6**

### Property 7: JWT expiry enforced
For any access token T with `exp` in the past, any API request using T must return HTTP 401.

**Validates: Requirements 3.1, 14.1**

### Property 8: Rate limit enforced
For any IP address that submits 6 or more login requests within 10 minutes, the 6th and subsequent requests within the block window must return HTTP 429.

**Validates: Requirements 1.8, 14.3**

---

## Error Handling

| Scenario | HTTP Status | Response |
|---|---|---|
| Missing or invalid JWT | 401 | `{"detail": "Not authenticated"}` |
| JWT signature invalid | 401 | `{"detail": "Invalid token"}` |
| Resource not owned by user | 403 | `{"detail": "Not found"}` (deliberately vague) |
| Resource not found (own) | 404 | `{"detail": "Not found"}` |
| Duplicate email on signup | 409 | `{"detail": "Email already registered"}` |
| Duplicate project name | 409 | `{"detail": "Project name already in use"}` |
| Rate limit exceeded | 429 | `{"detail": "Too many requests, try again later"}` |
| Wrong current password | 400 | `{"detail": "Current password is incorrect"}` |
| Unsupported file type | 422 | `{"detail": "Unsupported file type '...'"}` |
| File too large | 413 | `{"detail": "File exceeds 20 MB limit"}` |
| Missing env var at startup | — | Log + `sys.exit(1)` |

The frontend maps all API errors to user-facing toast messages. Raw tracebacks are never shown.

---

## Testing Strategy

### Unit Tests (pytest)

- `auth/service.py` — `hash_password`, `verify_password`, `create_access_token`, `verify_access_token`
- `projects/service.py` — `get_project_for_user` returns 403 for wrong user
- `storage/local.py` — save/get_url/delete round-trip
- `analytics/service.py` — opt-out check, event recording

### Integration Tests (pytest + httpx AsyncClient)

- Sign up → login → create project → upload image → run OCR → export → delete project (full lifecycle)
- Cross-user access: User A attempts to GET/PATCH/DELETE User B's project → expects 403
- Token refresh: expired access token → refresh → new token works
- Rate limiting: 6 rapid login attempts → 6th returns 429
- Cascade delete: delete project → images and annotations gone

### Frontend Tests (Vitest)

- `LoginForm` — renders email/password fields, shows error on failed submit
- `ProjectCard` — renders name, counts, relative timestamp
- `ProtectedLayout` — redirects to `/login` when no session
- `api.ts` — attaches Authorization header, handles 401 by triggering re-auth
