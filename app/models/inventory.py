from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric
from app.core.database import Base

class ProductInventory(Base):
    __tablename__ = "product_inventory"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    price = Column(Numeric(12,2))
    quantity = Column(Integer, default=0)