"""§3 Screen 9 Admin User Management contract."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import UserRole
from app.schemas.auth import UserResponse


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    # Plain str, not EmailStr, to match UserResponse.email and avoid adding
    # the optional `email-validator` dependency for a field the rest of the
    # codebase already treats as a plain string.
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    role: UserRole
    district: str | None = None


class UserUpdateRequest(BaseModel):
    """Partial update — only role/district/active are assignable from this screen.
    Username/email/password changes are out of scope for §3 Screen 9."""
    role: UserRole | None = None
    district: str | None = None
    is_active: bool | None = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
