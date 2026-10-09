# -*- coding: utf-8 -*-
"""
Marathi Scene Text Annotation Platform - Backend
FastAPI + SQLite (aiosqlite) — data survives restarts.

OCR fixes applied for Python 3.14 + PyTorch 2.6 on Windows:
  1. Pre-load transformers AutoImageProcessor BEFORE shapely/GEOS to avoid DLL conflict.
  2. Monkey-patch torch.load to pass weights_only=False for .ckpt/.pth files so
     PyTorch Lightning can load PARseq checkpoints under the new PyTorch 2.6 default.
"""
import os, sys, uuid, shutil, logging, random, asyncio, warnings, json, secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# ── Silence noisy warnings early ─────────────────────────────────────────────
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("MPLBACKEND", "Agg")

import aiosqlite
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from PIL import Image as PILImage

# ── IndicPhotoOCR path ────────────────────────────────────────────────────────
INDIC_PATH = str(Path("D:/AUS_TEXT/IndicPhotoOCR").resolve())
if INDIC_PATH not in sys.path:
    sys.path.insert(0, INDIC_PATH)

# ── Project layout paths ──────────────────────────────────────────────────────
# D:\AUS_TEXT\
#   app\          ← this running application
#   models\       ← marathi_finetuned.ckpt, marathi_combined.ckpt
#   android\      ← model_contract.json, .pt / .onnx exports
#   training\     ← benchmark/finetune scripts
AUS_ROOT    = Path("D:/AUS_TEXT")
MODELS_DIR  = AUS_ROOT / "models"
ANDROID_DIR = AUS_ROOT / "android"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── JWT config ────────────────────────────────────────────────────────────────
JWT_SECRET    = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24 * 7   # 7 days

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "annotations.db"
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ── SQLite schema ─────────────────────────────────────────────────────────────
SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    filename          TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    width             INTEGER,
    height            INTEGER,
    status            TEXT NOT NULL DEFAULT 'uploaded',
    upload_date       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
    id          TEXT PRIMARY KEY,
    image_id    TEXT NOT NULL REFERENCES images(id),
    x1          REAL NOT NULL,
    y1          REAL NOT NULL,
    x2          REAL NOT NULL,
    y2          REAL NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    label       TEXT NOT NULL DEFAULT 'Marathi',
    confidence  REAL NOT NULL DEFAULT 1.0,
    accepted    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'annotator',
    created_at   TEXT NOT NULL
);
"""

# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    return db

async def fetchall(db, sql, params=()):
    async with db.execute(sql, params) as cur:
        return await cur.fetchall()

async def fetchone(db, sql, params=()):
    async with db.execute(sql, params) as cur:
        return await cur.fetchone()

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    db = await get_db()
    await db.close()
    log.info("Database ready at %s", DB_PATH)

    # Pre-load IndicPhotoOCR in background so first OCR click is instant
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _init_ocr_sync)
    log.info("IndicPhotoOCR loading in background — first OCR call will wait for it")

    yield

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Marathi Scene Text Annotation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/images", StaticFiles(directory=IMAGES_DIR), name="images")

# ── OCR engine (lazy, thread-pool) ────────────────────────────────────────────
_ocr_engine = None
_ocr_error  = None
_ocr_lock   = asyncio.Lock()
_executor   = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
_ocr_progress_subscribers: dict[str, set[asyncio.Queue]] = {}


def publish_ocr_progress(project_id: str, event_type: str, **data) -> None:
    """Fan out a batch OCR progress event to SSE clients for one project."""
    event = {"type": event_type, "project_id": project_id, **data}
    for queue in list(_ocr_progress_subscribers.get(project_id, set())):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def _apply_ocr_patches():
    """
    Two patches needed on Python 3.14 + PyTorch 2.6 + Windows:

    PATCH 1 — DLL conflict:
      shapely's GEOS DLL conflicts with the torchvision C-runtime used by
      transformers AutoImageProcessor when loaded in a specific order.
      Fix: pre-load the VIT processor *before* shapely is imported.

    PATCH 2 — weights_only default changed in PyTorch 2.6:
      torch.load now defaults to weights_only=True which rejects PARseq .ckpt files.
      Fix: register safe globals AND monkey-patch torch.load at the serialization
      module level so PyTorch Lightning's internal import also picks it up.
    """
    import torch
    import torch.serialization as _tser

    # PATCH 2a: register safe globals used by PARseq checkpoints
    try:
        torch.serialization.add_safe_globals([getattr])
        log.info("Patch 2a applied: added getattr to torch safe globals")
    except Exception as e:
        log.warning("Patch 2a partial: %s", e)

    # PATCH 2b: patch torch.load at the module level so ALL callers
    # (including pytorch_lightning.cloud_io which imports torch separately)
    # get weights_only=False for checkpoint files
    _orig_load = torch.load
    def _safe_load(f, *args, **kwargs):
        path = str(f) if not hasattr(f, "read") else ""
        if any(path.endswith(ext) for ext in (".ckpt", ".pth", ".pth.tar", ".pt")):
            kwargs.setdefault("weights_only", False)
        return _orig_load(f, *args, **kwargs)
    torch.load = _safe_load

    # Patch lightning_fabric's cloud_io._load which calls torch.load internally
    try:
        import lightning_fabric.utilities.cloud_io as _cloud_io
        _orig_cloud_load = _cloud_io._load
        def _patched_cloud_load(path_or_url, map_location=None, weights_only=True):
            # Override weights_only=False so .ckpt files load correctly
            return _orig_cloud_load(path_or_url, map_location=map_location, weights_only=False)
        _cloud_io._load = _patched_cloud_load
        log.info("Patch 2b applied: lightning_fabric cloud_io._load patched")
    except Exception as e:
        log.warning("Patch 2b partial (cloud_io): %s", e)

    log.info("Patch 2 applied: torch.load weights_only=False on checkpoints")

    # PATCH 1: pre-load AutoImageProcessor before any GEOS/shapely import
    from transformers import AutoImageProcessor
    _cached_proc = AutoImageProcessor.from_pretrained(
        "google/vit-base-patch16-224-in21k", use_fast=False
    )
    _orig_from_pretrained = AutoImageProcessor.from_pretrained
    def _cached_from_pretrained(model_name_or_path, **kwargs):
        if "vit-base-patch16-224-in21k" in str(model_name_or_path):
            return _cached_proc
        return _orig_from_pretrained(model_name_or_path, **kwargs)
    AutoImageProcessor.from_pretrained = _cached_from_pretrained
    log.info("Patch 1 applied: AutoImageProcessor pre-loaded and cached")


def _init_ocr_sync():
    """Blocking init — runs in executor thread, never blocks the event loop."""
    global _ocr_engine, _ocr_error
    try:
        log.info("Applying OCR patches…")
        _apply_ocr_patches()

        log.info("Loading IndicPhotoOCR engine…")
        from IndicPhotoOCR.ocr import OCR
        _ocr_engine = OCR(verbose=False, identifier_lang="auto", device="cpu")
        log.info("IndicPhotoOCR engine ready.")
    except Exception as exc:
        import traceback
        _ocr_error = str(exc)
        log.error("IndicPhotoOCR init failed:\n%s", traceback.format_exc())


async def get_ocr_engine():
    global _ocr_engine, _ocr_error
    if _ocr_error:
        return None
    if _ocr_engine is not None:
        return _ocr_engine
    async with _ocr_lock:
        if _ocr_engine is None and not _ocr_error:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_executor, _init_ocr_sync)
    return _ocr_engine if not _ocr_error else None

# ── Auth helpers ──────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _check_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _create_token(user_id: str, email: str, name: str, role: str) -> str:
    from jose import jwt as jose_jwt
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_TTL_HOURS),
    }
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> dict:
    from jose import jwt as jose_jwt, JWTError
    try:
        return jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

_bearer = HTTPBearer(auto_error=False)

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode_token(creds.credentials)

# ── Auth schemas ───────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# ── Schemas ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class Project(BaseModel):
    id: str; name: str; description: str; status: str
    created_at: str; image_count: int = 0

class ImageInfo(BaseModel):
    id: str; project_id: str; filename: str; original_filename: str
    width: Optional[int] = None; height: Optional[int] = None
    status: str; upload_date: str; file_url: str

class AnnotationCreate(BaseModel):
    image_id: str
    x1: float; y1: float; x2: float; y2: float
    text: str = ""; label: str = "Marathi"

class Annotation(BaseModel):
    id: str; image_id: str
    x1: float; y1: float; x2: float; y2: float
    text: str; label: str
    confidence: float = 1.0; accepted: bool = True; created_at: str

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat()

def _label_for(text: str) -> str:
    if not text: return "Marathi"
    if any(0x0900 <= ord(c) <= 0x097F for c in text): return "Marathi"
    if text.replace(".", "").replace(",", "").isdigit() or "\u20b9" in text or "%" in text:
        return "Numeric"
    if all(ord(c) < 128 for c in text): return "English"
    return "Mixed"

def _row_to_project(row, image_count=0) -> Project:
    return Project(id=row["id"], name=row["name"], description=row["description"],
                   status=row["status"], created_at=row["created_at"],
                   image_count=image_count)

def _row_to_image(row) -> ImageInfo:
    return ImageInfo(id=row["id"], project_id=row["project_id"],
                     filename=row["filename"], original_filename=row["original_filename"],
                     width=row["width"], height=row["height"],
                     status=row["status"], upload_date=row["upload_date"],
                     file_url=f"/static/images/{row['filename']}")

def _row_to_annotation(row) -> Annotation:
    return Annotation(id=row["id"], image_id=row["image_id"],
                      x1=row["x1"], y1=row["y1"], x2=row["x2"], y2=row["y2"],
                      text=row["text"], label=row["label"],
                      confidence=row["confidence"], accepted=bool(row["accepted"]),
                      created_at=row["created_at"])

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "ocr_ready": _ocr_engine is not None,
            "ocr_error": _ocr_error}

# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/auth/signup")
async def signup(body: SignupRequest):
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db = await get_db()
    try:
        existing = await fetchone(db, "SELECT id FROM users WHERE email=?", (body.email.lower(),))
        if existing:
            raise HTTPException(400, "Email already registered")
        uid = str(uuid.uuid4())
        pw_hash = _hash_password(body.password)
        await db.execute(
            "INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)",
            (uid, body.name.strip(), body.email.lower(), pw_hash, "annotator", _now())
        )
        await db.commit()
        token = _create_token(uid, body.email.lower(), body.name.strip(), "annotator")
        return {"access_token": token, "token_type": "bearer",
                "user": {"id": uid, "name": body.name.strip(), "email": body.email.lower(), "role": "annotator"}}
    finally:
        await db.close()


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    db = await get_db()
    try:
        row = await fetchone(db, "SELECT * FROM users WHERE email=?", (body.email.lower(),))
        if not row or not _check_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        token = _create_token(row["id"], row["email"], row["name"], row["role"])
        return {"access_token": token, "token_type": "bearer",
                "user": {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}}
    finally:
        await db.close()


@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return {"id": user["sub"], "name": user["name"], "email": user["email"], "role": user["role"]}

# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/projects", response_model=List[Project])
async def list_projects():
    db = await get_db()
    try:
        rows = await fetchall(db, "SELECT * FROM projects ORDER BY created_at DESC")
        result = []
        for row in rows:
            c = await fetchone(db, "SELECT COUNT(*) as c FROM images WHERE project_id=?", (row["id"],))
            result.append(_row_to_project(row, c["c"]))
        return result
    finally:
        await db.close()

@app.post("/api/projects", response_model=Project)
async def create_project(body: ProjectCreate):
    db = await get_db()
    try:
        pid = str(uuid.uuid4()); now = _now()
        await db.execute("INSERT INTO projects(id,name,description,status,created_at) VALUES(?,?,?,?,?)",
                         (pid, body.name, body.description or "", "active", now))
        await db.commit()
        row = await fetchone(db, "SELECT * FROM projects WHERE id=?", (pid,))
        return _row_to_project(row, 0)
    finally:
        await db.close()

@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    db = await get_db()
    try:
        row = await fetchone(db, "SELECT * FROM projects WHERE id=?", (project_id,))
        if not row: raise HTTPException(404, "Project not found")
        c = await fetchone(db, "SELECT COUNT(*) as c FROM images WHERE project_id=?", (project_id,))
        return _row_to_project(row, c["c"])
    finally:
        await db.close()

# ── Images ────────────────────────────────────────────────────────────────────

async def _save_uploaded_file(project_id: str, file: UploadFile, db) -> ImageInfo:
    """Save one uploaded file to disk + DB. Returns ImageInfo."""
    file_id  = str(uuid.uuid4())
    ext      = Path(file.filename or "img.jpg").suffix.lower() or ".jpg"
    filename = f"{file_id}{ext}"
    dest     = IMAGES_DIR / filename
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    try:
        with PILImage.open(dest) as img:
            w, h = img.size
    except Exception:
        w, h = None, None
    now = _now()
    await db.execute(
        "INSERT INTO images(id,project_id,filename,original_filename,width,height,status,upload_date)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (file_id, project_id, filename, file.filename or "unknown", w, h, "uploaded", now)
    )
    return ImageInfo(id=file_id, project_id=project_id, filename=filename,
                     original_filename=file.filename or "unknown",
                     width=w, height=h, status="uploaded", upload_date=now,
                     file_url=f"/static/images/{filename}")


@app.post("/api/projects/{project_id}/images/upload", response_model=ImageInfo)
async def upload_image(project_id: str, file: UploadFile = File(...)):
    """Upload a single image."""
    db = await get_db()
    try:
        if not await fetchone(db, "SELECT id FROM projects WHERE id=?", (project_id,)):
            raise HTTPException(404, "Project not found")
        ct = file.content_type or ""
        if not ct.startswith("image/"):
            raise HTTPException(400, f"File must be an image, got: {ct}")
        info = await _save_uploaded_file(project_id, file, db)
        await db.commit()
        return info
    finally:
        await db.close()


@app.post("/api/projects/{project_id}/images/upload-bulk")
async def upload_images_bulk(project_id: str, files: List[UploadFile] = File(...)):
    """Upload multiple images at once. Returns list of results with per-file status."""
    db = await get_db()
    try:
        if not await fetchone(db, "SELECT id FROM projects WHERE id=?", (project_id,)):
            raise HTTPException(404, "Project not found")

        results = []
        for file in files:
            ct = file.content_type or ""
            if not ct.startswith("image/"):
                results.append({"filename": file.filename, "status": "skipped",
                                 "reason": f"not an image ({ct})"})
                continue
            try:
                info = await _save_uploaded_file(project_id, file, db)
                results.append({"filename": file.filename, "status": "ok",
                                 "image_id": info.id, "file_url": info.file_url})
            except Exception as exc:
                results.append({"filename": file.filename, "status": "error",
                                 "reason": str(exc)})

        await db.commit()
        ok_count = sum(1 for r in results if r["status"] == "ok")
        return {"uploaded": ok_count, "total": len(files), "results": results}
    finally:
        await db.close()


@app.get("/api/projects/{project_id}/images", response_model=List[ImageInfo])
async def list_project_images(project_id: str):
    db = await get_db()
    try:
        rows = await fetchall(db, "SELECT * FROM images WHERE project_id=? ORDER BY upload_date ASC",
                              (project_id,))
        return [_row_to_image(r) for r in rows]
    finally:
        await db.close()

@app.get("/api/images/{image_id}", response_model=ImageInfo)
async def get_image(image_id: str):
    db = await get_db()
    try:
        row = await fetchone(db, "SELECT * FROM images WHERE id=?", (image_id,))
        if not row: raise HTTPException(404, "Image not found")
        return _row_to_image(row)
    finally:
        await db.close()

@app.delete("/api/images/{image_id}")
async def delete_image(image_id: str):
    db = await get_db()
    try:
        row = await fetchone(db, "SELECT * FROM images WHERE id=?", (image_id,))
        if not row: raise HTTPException(404, "Image not found")
        dest = IMAGES_DIR / row["filename"]
        if dest.exists(): dest.unlink()
        await db.execute("DELETE FROM annotations WHERE image_id=?", (image_id,))
        await db.execute("DELETE FROM images WHERE id=?", (image_id,))
        await db.commit()
        return {"deleted": image_id}
    finally:
        await db.close()

# ── Annotations ───────────────────────────────────────────────────────────────

@app.get("/api/images/{image_id}/annotations", response_model=List[Annotation])
async def list_annotations(image_id: str):
    db = await get_db()
    try:
        rows = await fetchall(db, "SELECT * FROM annotations WHERE image_id=? ORDER BY created_at ASC",
                              (image_id,))
        return [_row_to_annotation(r) for r in rows]
    finally:
        await db.close()

@app.post("/api/images/{image_id}/annotations", response_model=Annotation)
async def create_annotation(image_id: str, body: AnnotationCreate):
    db = await get_db()
    try:
        if not await fetchone(db, "SELECT id FROM images WHERE id=?", (image_id,)):
            raise HTTPException(404, "Image not found")
        ann_id = str(uuid.uuid4()); now = _now()
        await db.execute(
            "INSERT INTO annotations(id,image_id,x1,y1,x2,y2,text,label,confidence,accepted,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ann_id, image_id, body.x1, body.y1, body.x2, body.y2,
             body.text, body.label, 1.0, 1, now))
        await db.commit()
        row = await fetchone(db, "SELECT * FROM annotations WHERE id=?", (ann_id,))
        return _row_to_annotation(row)
    finally:
        await db.close()

@app.put("/api/annotations/{annotation_id}", response_model=Annotation)
async def update_annotation(annotation_id: str, body: AnnotationCreate):
    db = await get_db()
    try:
        if not await fetchone(db, "SELECT id FROM annotations WHERE id=?", (annotation_id,)):
            raise HTTPException(404, "Annotation not found")
        await db.execute(
            "UPDATE annotations SET text=?,label=?,x1=?,y1=?,x2=?,y2=? WHERE id=?",
            (body.text, body.label, body.x1, body.y1, body.x2, body.y2, annotation_id))
        await db.commit()
        row = await fetchone(db, "SELECT * FROM annotations WHERE id=?", (annotation_id,))
        return _row_to_annotation(row)
    finally:
        await db.close()

@app.delete("/api/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str):
    db = await get_db()
    try:
        if not await fetchone(db, "SELECT id FROM annotations WHERE id=?", (annotation_id,)):
            raise HTTPException(404, "Annotation not found")
        await db.execute("DELETE FROM annotations WHERE id=?", (annotation_id,))
        await db.commit()
        return {"deleted": annotation_id}
    finally:
        await db.close()

# ── OCR ───────────────────────────────────────────────────────────────────────

async def _save_annotations_bulk(db, image_id: str, items: list) -> list:
    created = []
    for item in items:
        x1,y1,x2,y2 = item["x1"],item["y1"],item["x2"],item["y2"]
        if x2 <= x1 or y2 <= y1: continue
        ann_id = str(uuid.uuid4()); now = _now()
        label  = _label_for(item.get("text",""))
        conf   = float(item.get("confidence", 1.0))
        await db.execute(
            "INSERT INTO annotations(id,image_id,x1,y1,x2,y2,text,label,confidence,accepted,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ann_id, image_id, x1, y1, x2, y2, item.get("text",""), label, conf, 1, now))
        created.append(Annotation(id=ann_id, image_id=image_id,
                                  x1=x1, y1=y1, x2=x2, y2=y2,
                                  text=item.get("text",""), label=label,
                                  confidence=conf, accepted=True, created_at=now))
    await db.commit()
    return created


@app.post("/api/images/{image_id}/ocr")
async def run_ocr(image_id: str):
    return await _run_ocr_with_engine(image_id, engine="indic")


@app.post("/api/images/{image_id}/ocr/finetuned")
async def run_ocr_finetuned(image_id: str):
    return await _run_ocr_with_engine(image_id, engine="finetuned")


async def _run_ocr_with_engine(image_id: str, engine: str = "indic") -> dict:
    db = await get_db()
    try:
        img_row = await fetchone(db, "SELECT * FROM images WHERE id=?", (image_id,))
        if not img_row: raise HTTPException(404, "Image not found")
        image_path = IMAGES_DIR / img_row["filename"]
        if not image_path.exists(): raise HTTPException(404, "Image file missing from disk")

        try:
            if engine == "finetuned":
                # ── Finetuned recogniser ───────────────────────────────────
                # Use IndicPhotoOCR for detection, our checkpoint for recognition.
                # Loading pattern mirrors benchmark_finetuned.py exactly.
                ocr = await get_ocr_engine()
                if ocr is None:
                    raise RuntimeError(_ocr_error or "OCR engine unavailable")

                _AUS       = AUS_ROOT
                _INDIC     = Path(INDIC_PATH)
                _CKPT_BASE = _INDIC / "IndicPhotoOCR/recognition/models/marathi.ckpt"
                _CKPT_FT   = MODELS_DIR / "marathi_finetuned.ckpt"

                if not _CKPT_FT.exists():
                    raise RuntimeError(f"Finetuned checkpoint not found: {_CKPT_FT}")
                if not _CKPT_BASE.exists():
                    raise RuntimeError(f"Base checkpoint not found: {_CKPT_BASE}")

                loop = asyncio.get_event_loop()

                def _run_finetuned():
                    import torch, cv2, numpy as np
                    from torchvision import transforms as T
                    from PIL import Image as PILImage

                    # ── Load model (cached on app.state) ──────────────────
                    cache_key = str(_CKPT_FT)
                    if getattr(app.state, "_ft_model_key", None) != cache_key:
                        log.info("Loading finetuned model …")
                        sys.path.insert(0, str(_INDIC))

                        from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint

                        # Load architecture from base checkpoint, overlay finetuned weights
                        _m = load_from_checkpoint(str(_CKPT_BASE))
                        state = torch.load(str(_CKPT_FT), map_location="cpu", weights_only=False)
                        _m.load_state_dict(state["state_dict"])
                        _m = _m.cpu().eval()

                        app.state._ft_model     = _m
                        app.state._ft_model_key = cache_key
                        log.info("Finetuned model loaded.")

                    ft_model = app.state._ft_model
                    hp       = ft_model.hparams

                    transform = T.Compose([
                        T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
                        T.ToTensor(),
                        T.Normalize(0.5, 0.5),
                    ])

                    image_cv   = cv2.imread(str(image_path))
                    detections = ocr.detect(str(image_path))
                    results    = []

                    for bbox in detections:
                        pts  = np.array(bbox)
                        x1i  = int(pts[:,0].min()); y1i = int(pts[:,1].min())
                        x2i  = int(pts[:,0].max()); y2i = int(pts[:,1].max())
                        x1c  = max(0, x1i);  y1c = max(0, y1i)
                        x2c  = min(image_cv.shape[1], x2i)
                        y2c  = min(image_cv.shape[0], y2i)
                        if x2c <= x1c or y2c <= y1c:
                            continue

                        # BGR → RGB PIL image → transform → inference
                        crop_bgr = image_cv[y1c:y2c, x1c:x2c]
                        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                        pil_crop = PILImage.fromarray(crop_rgb)

                        try:
                            tensor = transform(pil_crop).unsqueeze(0)   # [1,3,H,W]
                            with torch.no_grad():
                                logits = ft_model(tensor)                # [1,T,C]
                            probs  = logits.softmax(-1)
                            preds, confs = ft_model.tokenizer.decode(probs)
                            text   = ft_model.charset_adapter(preds[0])
                            conf   = float(confs[0].mean().item()) if hasattr(confs[0], 'mean') else float(confs[0])
                        except Exception as e:
                            log.warning("Finetuned recognition failed for crop: %s", e)
                            continue

                        results.append({
                            "x1": x1i, "y1": y1i, "x2": x2i, "y2": y2i,
                            "text": text,
                            "confidence": min(max(conf, 0.0), 1.0),
                        })

                    return results

                items   = await loop.run_in_executor(_executor, _run_finetuned)
                created = await _save_annotations_bulk(db, image_id, items)
                await db.execute("UPDATE images SET status=? WHERE id=?", ("ocr_completed", image_id))
                await db.commit()
                log.info("Finetuned OCR: %d annotations for %s", len(created), image_id)
                return {"engine": "Finetuned (Marathi)",
                        "message": f"Finetuned OCR complete — {len(created)} annotations created",
                        "annotations": created}

            else:
                # ── IndicPhotoOCR (default) ────────────────────────────────
                ocr = await get_ocr_engine()
                if ocr is None:
                    raise RuntimeError(_ocr_error or "OCR engine unavailable")

                loop = asyncio.get_event_loop()

                def _run_inference():
                    import cv2, numpy as np
                    image_cv   = cv2.imread(str(image_path))
                    detections = ocr.detect(str(image_path))
                    results    = []
                    for bbox in detections:
                        script_lang, crop = ocr.crop_and_identify_script(image_cv, bbox)
                        if not script_lang or not crop: continue
                        text, conf = ocr.recognise(crop, script_lang, return_confidence=True)
                        pts = np.array(bbox)
                        results.append({
                            "x1": int(pts[:,0].min()), "y1": int(pts[:,1].min()),
                            "x2": int(pts[:,0].max()), "y2": int(pts[:,1].max()),
                            "text": text, "confidence": float(conf),
                        })
                        try: os.remove(crop)
                        except OSError: pass
                    return results

                items   = await loop.run_in_executor(_executor, _run_inference)
                created = await _save_annotations_bulk(db, image_id, items)
                await db.execute("UPDATE images SET status=? WHERE id=?", ("ocr_completed", image_id))
                await db.commit()
                log.info("IndicPhotoOCR: %d annotations for %s", len(created), image_id)
                return {"engine": "IndicPhotoOCR",
                        "message": f"OCR complete — {len(created)} annotations created",
                        "annotations": created}

        except Exception as exc:
            log.warning("OCR failed (%s), using mock", exc)
            items   = _mock_items(img_row["width"] or 400, img_row["height"] or 300)
            created = await _save_annotations_bulk(db, image_id, items)
            await db.execute("UPDATE images SET status=? WHERE id=?", ("ocr_completed", image_id))
            await db.commit()
            return {"engine": "mock",
                    "message": f"Mock OCR — {len(created)} annotations",
                    "note": str(exc), "annotations": created}
    finally:
        await db.close()


async def _run_batch_ocr(project_id: str, image_ids: list[str]) -> None:
    """Run project images serially and publish progress without blocking the request."""
    total = len(image_ids)
    completed = failed = 0
    publish_ocr_progress(project_id, "batch_ocr_started", total=total, completed=0, failed=0)

    for image_id in image_ids:
        try:
            result = await run_ocr(image_id)
            completed += 1
            publish_ocr_progress(
                project_id,
                "batch_ocr_progress",
                image_id=image_id,
                completed=completed,
                failed=failed,
                total=total,
                engine=result.get("engine"),
            )
        except Exception as exc:
            failed += 1
            log.exception("Batch OCR failed for image %s", image_id)
            publish_ocr_progress(
                project_id,
                "batch_ocr_image_failed",
                image_id=image_id,
                error=str(exc),
                completed=completed,
                failed=failed,
                total=total,
            )

    publish_ocr_progress(
        project_id,
        "batch_ocr_finished",
        completed=completed,
        failed=failed,
        total=total,
    )


@app.post("/api/projects/{project_id}/ocr-all")
async def run_project_ocr(project_id: str, background_tasks: BackgroundTasks):
    """Queue OCR for every uploaded image in a project."""
    db = await get_db()
    try:
        project = await fetchone(db, "SELECT id FROM projects WHERE id=?", (project_id,))
        if not project:
            raise HTTPException(404, "Project not found")
        rows = await fetchall(
            db,
            "SELECT id FROM images WHERE project_id=? AND status=? ORDER BY upload_date ASC",
            (project_id, "uploaded"),
        )
    finally:
        await db.close()

    image_ids = [row["id"] for row in rows]
    if not image_ids:
        return {"queued": 0, "message": "No images pending OCR"}

    background_tasks.add_task(_run_batch_ocr, project_id, image_ids)
    return {"queued": len(image_ids), "message": f"OCR queued for {len(image_ids)} images"}


@app.get("/api/projects/{project_id}/ocr-progress")
async def stream_project_ocr_progress(project_id: str):
    """Stream live OCR batch status for one project as server-sent events."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    subscribers = _ocr_progress_subscribers.setdefault(project_id, set())
    subscribers.add(queue)

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\\n\\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\\n\\n"
        finally:
            subscribers.discard(queue)
            if not subscribers:
                _ocr_progress_subscribers.pop(project_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _mock_items(W: int, H: int) -> list:
    WORDS = [
        "\u092e\u0930\u093e\u0920\u0940", "\u092d\u093e\u0937\u093e",
        "\u0926\u0948\u0928\u093f\u0915", "\u0935\u0943\u0924\u094d\u0924\u092a\u0924\u094d\u0930",
        "\u092e\u0939\u093e\u0930\u093e\u0937\u094d\u091f\u094d\u0930",
        "\u092e\u0941\u0902\u092c\u0908", "\u092a\u0941\u0923\u0947",
        "News", "Today", "Sports", "Update", "123", "456", "\u20b9500", "2024",
    ]
    items, row_y = [], 20
    while row_y < H - 30 and len(items) < 20:
        x, row_h = 15, random.randint(22, 36)
        while x < W - 60:
            word  = random.choice(WORDS)
            box_w = max(40, len(word) * random.randint(9, 13))
            if x + box_w > W - 10: break
            items.append({"x1": x, "y1": row_y, "x2": x+box_w, "y2": row_y+row_h,
                          "text": word, "confidence": random.uniform(0.72, 0.97)})
            x += box_w + random.randint(6, 18)
        row_y += row_h + random.randint(10, 22)
    return items

# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/export")
async def export_project(project_id: str, format: str = "json"):
    LABEL_ID = {"Marathi": 0, "English": 1, "Numeric": 2, "Mixed": 3, "Logo": 4}
    db = await get_db()
    try:
        images = await fetchall(db, "SELECT * FROM images WHERE project_id=? ORDER BY upload_date",
                                (project_id,))
        if not images: raise HTTPException(404, "No images in this project")
        result = {"project_id": project_id, "export_format": format,
                  "export_date": _now(), "images": []}
        for img in images:
            anns = await fetchall(db, "SELECT * FROM annotations WHERE image_id=?", (img["id"],))
            if format == "yolo" and img["width"] and img["height"]:
                rows = []
                for a in anns:
                    xc = ((a["x1"]+a["x2"])/2)/img["width"]
                    yc = ((a["y1"]+a["y2"])/2)/img["height"]
                    bw = (a["x2"]-a["x1"])/img["width"]
                    bh = (a["y2"]-a["y1"])/img["height"]
                    rows.append(f"{LABEL_ID.get(a['label'],0)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                result["images"].append({"filename": img["original_filename"], "annotations": rows})
            elif format == "coco":
                result["images"].append({
                    "id": img["id"], "filename": img["original_filename"],
                    "width": img["width"], "height": img["height"],
                    "annotations": [{"id": i+1, "image_id": img["id"],
                        "category_id": LABEL_ID.get(a["label"],0)+1,
                        "bbox": [a["x1"],a["y1"],a["x2"]-a["x1"],a["y2"]-a["y1"]],
                        "area": (a["x2"]-a["x1"])*(a["y2"]-a["y1"]),
                        "text": a["text"], "confidence": a["confidence"]}
                     for i, a in enumerate(anns)]})
            else:
                result["images"].append({
                    "id": img["id"], "filename": img["original_filename"],
                    "width": img["width"], "height": img["height"],
                    "annotations": [{"id": a["id"], "x1": a["x1"], "y1": a["y1"],
                        "x2": a["x2"], "y2": a["y2"], "text": a["text"],
                        "label": a["label"], "confidence": a["confidence"],
                        "accepted": bool(a["accepted"]), "created_at": a["created_at"]}
                     for a in anns]})
        return result
    finally:
        await db.close()

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/stats")
async def project_stats(project_id: str):
    db = await get_db()
    try:
        images  = await fetchall(db, "SELECT id FROM images WHERE project_id=?", (project_id,))
        img_ids = [i["id"] for i in images]
        if not img_ids:
            return {"total_images": 0, "total_annotations": 0, "completion_rate": 0,
                    "average_confidence": 0, "high_confidence_annotations": 0,
                    "low_confidence_annotations": 0, "annotations_per_image": 0,
                    "label_distribution": {}, "images_with_annotations": 0,
                    "images_without_annotations": 0}
        ph   = ",".join("?" * len(img_ids))
        anns = await fetchall(db, f"SELECT * FROM annotations WHERE image_id IN ({ph})", img_ids)
        n    = len(anns)
        imgs_with = len({a["image_id"] for a in anns})
        avg_conf  = sum(a["confidence"] for a in anns) / n if n else 0
        label_dist: dict = {}
        for a in anns: label_dist[a["label"]] = label_dist.get(a["label"], 0) + 1
        return {
            "total_images": len(images), "images_with_annotations": imgs_with,
            "images_without_annotations": len(images)-imgs_with,
            "total_annotations": n, "average_confidence": round(avg_conf, 3),
            "high_confidence_annotations": sum(1 for a in anns if a["confidence"] > 0.9),
            "low_confidence_annotations":  sum(1 for a in anns if a["confidence"] < 0.7),
            "annotations_per_image": round(n/len(images), 2),
            "label_distribution": label_dist,
            "completion_rate": round(imgs_with/len(images)*100, 1),
        }
    finally:
        await db.close()
