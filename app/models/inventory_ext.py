from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(150), nullable=False)
    email = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), default="pending")
    # pending | ordered | received | cancelled
    order_date = Column(Date, nullable=False)
    expected_date = Column(Date, nullable=True)
    received_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True)
    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("product_inventory.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_name = Column(String(150), nullable=False)
    # Store name separately so it survives product deletion.
    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, default=0)
    unit_cost = Column(Numeric(12, 2), nullable=False)
