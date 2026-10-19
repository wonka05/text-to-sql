from sqlalchemy import Column, Date, Integer, String

from app.database.base import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True)
    customer_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    city = Column(String(50))
    phone = Column(String(20))
    join_date = Column(Date)
