import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.enums import UserRole

class LoginRequest(BaseModel):
    username: str  # Accepts either username or email
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    role: UserRole
    district: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenPayload(BaseModel):
    sub: str
    lmo_id: str
    role: UserRole
    district: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
