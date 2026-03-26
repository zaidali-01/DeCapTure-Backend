from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Sales(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    payment_method = Column(String(50))
    salesman_id = Column(Integer, ForeignKey("users.id"))
    transaction_id = Column(String(150))


class SalesInventoryBridge(Base):
    __tablename__ = "sales_inventory_bridge"

    id = Column(Integer, primary_key=True)
    sales_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"))
    listing_id = Column(Integer, ForeignKey("product_inventory.id"))
    quantity = Column(Integer)