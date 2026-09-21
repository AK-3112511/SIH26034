"""Users router for user lookup and field officer querying per §5.3."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_senior_lmo
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/field-officers", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
def list_field_officers(
    district: Optional[str] = Query(None, description="Optional district filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """List active field officers available for task assignment per §5.3.
    
    Accessible to senior LMOs and admins for deploying field follow-ups.
    """
    query = db.query(User).filter(
        User.role == UserRole.FIELD_LMO,
        User.is_active == True,
    )
    if district:
        query = query.filter(User.district == district)
        
    return query.order_by(User.full_name.asc()).all()
