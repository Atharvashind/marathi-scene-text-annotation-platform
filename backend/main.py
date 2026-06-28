import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Marathi Scene Text Annotation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers.images import router as images_router
from backend.routers.ocr import router as ocr_router
from backend.routers.annotations import router as annotations_router
from backend.routers.metrics import router as metrics_router
from backend.routers.export import router as export_router
from backend.routers.events import router as events_router

app.include_router(images_router)
app.include_router(ocr_router)
app.include_router(annotations_router)
app.include_router(metrics_router)
app.include_router(export_router)
app.include_router(events_router)
