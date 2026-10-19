from sqlalchemy import DECIMAL, Column, Date, ForeignKey, Integer

from app.database.base import Base


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.customer_id", ondelete="CASCADE")
    )
    order_date = Column(Date)
    total_amount = Column(DECIMAL(10, 2))
