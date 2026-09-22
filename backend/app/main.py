import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import admin, auth, challans, dashboard, events, files, products, scans, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup: recover orphaned scans and pre-load the vision models.

    Model loading happens on a background thread so the API answers health
    checks immediately; the first scan simply waits for the models if it
    arrives before warm-up finishes.
    """
    from app.services.pipeline_orchestrator import requeue_stale_processing, warm_up_engines

    if not settings.SKIP_STARTUP_TASKS:
        try:
            requeue_stale_processing()
        except Exception as exc:  # database may be unavailable at boot in dev
            logger.warning("Stale-scan recovery skipped: %s", exc)
        threading.Thread(target=warm_up_engines, name="vision-warmup", daemon=True).start()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS: explicit origins from settings; localhost on any port is allowed outside production.
# Never pair allow_origins=["*"] with allow_credentials=True — browsers block that.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=None if settings.is_production else r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local evidence directory.  Files are served only through the authenticated
# /api/v1/files endpoint — there is deliberately no public static mount.
os.makedirs(settings.STORAGE_LOCAL_DIR, exist_ok=True)

# Include domain routers
app.include_router(scans.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(challans.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(products.router, prefix=settings.API_V1_STR)
app.include_router(events.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(files.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "system": "MetrologyAI Backend API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }
