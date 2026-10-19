from sqlalchemy import DECIMAL, Column, ForeignKey, Integer

from app.database.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id", ondelete="CASCADE")
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE")
    )
    quantity = Column(Integer)
    unit_price = Column(DECIMAL(10, 2))
