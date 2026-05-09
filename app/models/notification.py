from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=True,
    )
    type = Column(String(60), nullable=False)
    # low_stock | leave_request | escalation | followup_due
    # po_received | lead_assigned | sale_made
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    entity_type = Column(String(60), nullable=True)
    entity_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
