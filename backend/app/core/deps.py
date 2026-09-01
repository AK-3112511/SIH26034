import uuid
from typing import List, Callable
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.auth import TokenPayload

security = HTTPBearer(auto_error=True)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Validate Bearer JWT token and retrieve the active user."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload_data = decode_access_token(token)
        lmo_id: str = payload_data.get("lmo_id") or payload_data.get("sub")
        if lmo_id is None:
            raise credentials_exception
        user_uuid = uuid.UUID(lmo_id)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC).

    Usage:
        @router.get("/protected", dependencies=[Depends(require_roles(UserRole.SENIOR_LMO, UserRole.ADMIN))])
        def review_endpoint(current_user: User = Depends(require_roles(UserRole.SENIOR_LMO))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            role_names = ", ".join(r.value for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of the following roles: [{role_names}]. Current role: '{current_user.role.value}'"
            )
        return current_user

    return role_checker


# Pre-built convenience role guards
require_field_lmo = require_roles(UserRole.FIELD_LMO)
require_senior_lmo = require_roles(UserRole.SENIOR_LMO, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
