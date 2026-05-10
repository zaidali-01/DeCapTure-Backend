from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, String, Numeric, Boolean
from sqlalchemy.sql import func

from app.core.database import Base


class StoreListing(Base):
    __tablename__ = "store_listings"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_inventory.id", ondelete="CASCADE"), nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    listing_type = Column(String(20), default="product", nullable=False)
    headline = Column(String(180), nullable=True)
    display_description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class StoreListingImage(Base):
    __tablename__ = "store_listing_images"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("store_listings.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class StoreOrder(Base):
    __tablename__ = "store_orders"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    buyer_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    fulfilled_sale_id = Column(Integer, ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    buyer_name = Column(String(150), nullable=False)
    buyer_phone = Column(String(30), nullable=False)
    buyer_email = Column(String(150), nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class StoreOrderItem(Base):
    __tablename__ = "store_order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("store_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_inventory.id", ondelete="SET NULL"), nullable=True)
    product_name_snapshot = Column(String(150), nullable=False)
    unit_price_snapshot = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
