from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id = Column(
        Integer,
        ForeignKey("customer_contact.contact_id", ondelete="SET NULL"),
        nullable=True,
    )
    name = Column(String(150), nullable=False)
    email = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    source = Column(String(80))
    stage = Column(String(50), default="new")
    # new | contacted | qualified | proposal | won | lost
    value = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id = Column(
        Integer,
        ForeignKey("customer_contact.contact_id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
    )
    contact_id = Column(
        Integer,
        ForeignKey("customer_contact.contact_id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    due_date = Column(Date, nullable=False)
    is_done = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
