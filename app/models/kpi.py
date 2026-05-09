from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.sql import func

from app.core.database import Base


class KPITarget(Base):
    __tablename__ = "kpi_targets"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    revenue_target = Column(Numeric(14, 2), default=0)
    sales_target = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
