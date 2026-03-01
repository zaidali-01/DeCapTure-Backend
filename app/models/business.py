from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.core.database import Base

class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    industry = Column(String(100))
    description = Column(Text)
    phone = Column(String(20))
    email = Column(String(120))


class UserBusinessBridge(Base):
    __tablename__ = "user_business_bridge"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))