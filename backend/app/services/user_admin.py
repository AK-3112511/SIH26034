"""§3 Screen 9 Admin User Management — list/create/update users.

Deliberately narrow: role/district/active are the only fields this screen
can change on an existing user (per the blueprint's own scope: "Assign
field_lmo/senior_lmo/admin roles, assign district/zone"). Username, email,
and password are not editable from here.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user_admin import UserCreateRequest, UserUpdateRequest


class DuplicateUserError(Exception):
    """Raised when username or email is already taken."""


class UserNotFoundError(Exception):
    pass


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def create_user(db: Session, payload: UserCreateRequest) -> User:
    existing = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing is not None:
        raise DuplicateUserError(
            f"Username '{payload.username}' or email '{payload.email}' is already in use"
        )

    user = User(
        id=uuid.uuid4(),
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        district=payload.district,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UserNotFoundError(f"User '{user_id}' not found")

    if payload.role is not None:
        user.role = payload.role
    if payload.district is not None:
        user.district = payload.district
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user
