from sqlalchemy import DECIMAL, Column, Integer, String

from app.database.base import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True)
    product_name = Column(String(100), nullable=False)
    category = Column(String(50))
    price = Column(DECIMAL(10, 2), nullable=False)
    stock_quantity = Column(Integer, nullable=False)
