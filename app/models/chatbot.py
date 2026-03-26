from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, String
from sqlalchemy.sql import func
from app.core.database import Base


class BusinessDocument(Base):
    """Stores uploaded PDF paths per business."""
    __tablename__ = "business_documents"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)               # path on disk
    uploaded_at = Column(DateTime, server_default=func.now())


class ChatSession(Base):
    """A conversation thread between a customer and a business chatbot."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    customer_name = Column(String(150))
    created_at = Column(DateTime, server_default=func.now())


class ChatMessage(Base):
    """Individual messages inside a chat session."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role = Column(String(20), nullable=False)              # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())