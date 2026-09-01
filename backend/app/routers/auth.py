from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.core.security import verify_password, create_access_token
from app.core.deps import get_current_user
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate an LMO user (mobile or web client) and issue a signed JWT."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Match against either username or email
    user = db.query(User).filter(
        or_(
            User.username == login_data.username,
            User.email == login_data.username
        )
    ).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        # Audit log failed login attempt
        log_audit(
            db=db,
            action="USER_LOGIN_FAILED",
            target_type="user",
            actor_id=user.id if user else None,
            target_id=str(user.id) if user else None,
            detail={
                "attempted_identifier": login_data.username,
                "ip_address": client_ip,
                "user_agent": user_agent,
                "reason": "Invalid credentials"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_audit(
            db=db,
            action="USER_LOGIN_FAILED",
            target_type="user",
            actor_id=user.id,
            target_id=str(user.id),
            detail={
                "ip_address": client_ip,
                "user_agent": user_agent,
                "reason": "Account is inactive"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Issue JWT with lmo_id, role, and district
    access_token = create_access_token(
        lmo_id=str(user.id),
        role=user.role.value,
        district=user.district
    )

    # Audit log successful login event
    log_audit(
        db=db,
        action="USER_LOGIN_SUCCESS",
        target_type="user",
        actor_id=user.id,
        target_id=str(user.id),
        detail={
            "role": user.role.value,
            "district": user.district,
            "ip_address": client_ip,
            "user_agent": user_agent
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve current authenticated LMO user profile and verified claims."""
    return UserResponse.model_validate(current_user)
