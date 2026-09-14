import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import admin, auth, challans, scans

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Enable CORS for Web Dashboard (localhost and 127.0.0.1 are different origins).
# Do not pair allow_origins=["*"] with allow_credentials=True — browsers block that.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure local uploads directory exists and mount static route
os.makedirs(settings.STORAGE_LOCAL_DIR, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=settings.STORAGE_LOCAL_DIR), name="uploads")

# Include domain routers
app.include_router(scans.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(challans.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "system": "MetrologyAI Backend API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }
