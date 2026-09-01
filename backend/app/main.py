import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.routers import scans, auth, challans, admin

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
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
