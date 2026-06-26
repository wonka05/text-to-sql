from sqlalchemy import Column, Integer, String, DECIMAL
from app.database.base import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(100), nullable=False)
    category = Column(String(50))
    price = Column(DECIMAL(10, 2))
    stock_quantity = Column(Integer)