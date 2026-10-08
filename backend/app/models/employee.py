from sqlalchemy import Column, Integer, String, Date, DECIMAL, ForeignKey
from app.database.base import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True)

    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True)
    phone = Column(String(20))

    salary = Column(DECIMAL(10, 2), nullable=False)

    hire_date = Column(Date)

    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="SET NULL")
    )