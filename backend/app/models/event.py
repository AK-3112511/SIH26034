from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class EventLog(Base):
    """Real-time event transport log per §6.2.
    
    Retained for 7 days for client catchup, then pruned by retention cleanup.
    """
    __tablename__ = "event_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_district: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    target_role: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    target_user: Mapped[User | None] = relationship("User", foreign_keys=[target_user_id])

    __table_args__ = (
        Index("idx_event_logs_created_at", "created_at"),
        Index("idx_event_logs_target", "target_user_id", "target_district", "target_role"),
    )
