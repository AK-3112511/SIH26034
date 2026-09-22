"""Authenticated evidence download endpoint (see ``app.services.files``)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.services.files import guess_media_type, storage_key, verify_file_signature
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/files", tags=["files"])

_optional_bearer = HTTPBearer(auto_error=False)


@router.get("/{key}")
def download_file(
    key: str,
    request: Request,
    exp: int | None = Query(None),
    sig: str | None = Query(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
):
    """Serve a stored evidence file.

    Access is granted by either a valid signed ``exp``/``sig`` pair (issued in
    API responses) or a bearer token belonging to an active user.
    """
    key = storage_key(key)
    authorised = verify_file_signature(key, exp, sig)
    if not authorised and credentials is not None:
        # Raises 401/403 itself when the token is invalid.
        get_current_user(credentials=credentials, db=db)
        authorised = True
    if not authorised:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Evidence link expired or invalid")

    try:
        data = get_storage_provider().get_file(key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return Response(
        content=data,
        media_type=guess_media_type(key),
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{key}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
