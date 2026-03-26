from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, String, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class BusinessDocument(Base):
    """
    Stores metadata about uploaded PDFs per business.
    The actual chunks + vectors are stored in ChromaDB, not here.
    """
    __tablename__ = "business_documents"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, server_default=func.now())


class CommunicationSession(Base):
    """
    A conversation thread between a customer and a business chatbot.
    Each session is tied to one business.
    """
    __tablename__ = "communication_sessions"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    customer_name = Column(String(150))
    created_at = Column(DateTime, server_default=func.now())


class CommunicationMessage(Base):
    """
    A single message inside a CommunicationSession.
    role is either 'user' or 'assistant'.
    sources stores the chunk snippets used to answer (for transparency).
    """
    __tablename__ = "communication_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("communication_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())