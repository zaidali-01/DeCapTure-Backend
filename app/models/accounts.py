from sqlalchemy import Column, Integer, ForeignKey, Date, Numeric
from app.core.database import Base

class DailyAccounts(Base):
    __tablename__ = "daily_accounts"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    date = Column(Date)
    cost = Column(Numeric(12,2))
    revenue = Column(Numeric(12,2))
    sales = Column(Integer)
    salary_cost = Column(Numeric(12,2))
    operational_cost = Column(Numeric(12,2))
    miscellaneous = Column(Numeric(12,2))