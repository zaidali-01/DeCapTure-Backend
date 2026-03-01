from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class ContactCredentials(Base):
    __tablename__ = "contact_credentials"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    whatsapp_token = Column(Text)
    smtp_token = Column(Text)


class CustomerContact(Base):
    __tablename__ = "customer_contact"

    contact_id = Column(Integer, primary_key=True)
    name = Column(String(150))
    email = Column(String(120))
    phone = Column(String(20))


class Communication(Base):
    __tablename__ = "communication"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("customer_contact.contact_id", ondelete="CASCADE"))
    message = Column(Text)
    date = Column(DateTime, server_default=func.now())