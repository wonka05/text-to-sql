from sqlalchemy import Column, Integer, String

from app.database.base import Base


class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True)
    department_name = Column(String(100), unique=True, nullable=False)
