from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    detail: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    # Relationships
    actor: Mapped[Optional[User]] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_audit_log_detail", "detail", postgresql_using="gin"),
    )
