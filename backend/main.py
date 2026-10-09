import logging
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Request size limit middleware ──────────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY = 25 * 1024 * 1024  # 25 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY:
            return Response("Request body too large", status_code=413)
        return await call_next(request)


# ── Lifespan: run Alembic migrations on startup ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running Alembic migrations…")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd="backend",
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(f"Alembic migration output: {result.stderr}")
        else:
            logger.info("Migrations applied successfully")
    except Exception as e:
        logger.warning(f"Alembic migration failed (continuing): {e}")
    yield


# ── App factory ────────────────────────────────────────────────────────────────

app = FastAPI(title="Marathi Scene Text Annotation API", lifespan=lifespan)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGIN.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}

# ── Routers ────────────────────────────────────────────────────────────────────

from backend.routers.images import router as images_router
from backend.routers.annotations import router as annotations_router
from backend.routers.ocr import router as ocr_router
from backend.routers.metrics import router as metrics_router
from backend.routers.export import router as export_router
from backend.routers.events import router as events_router

app.include_router(images_router)
app.include_router(annotations_router)
app.include_router(ocr_router)
app.include_router(metrics_router)
app.include_router(export_router)
app.include_router(events_router)
