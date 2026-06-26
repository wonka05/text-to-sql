from sqlalchemy import Column, Integer, String, Date, DECIMAL, ForeignKey
from app.database.base import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String(50))
    last_name = Column(String(50))
    email = Column(String(100))
    phone = Column(String(20))

    salary = Column(DECIMAL(10, 2))

    hire_date = Column(Date)

    department_id = Column(
        Integer,
        ForeignKey("departments.department_id")
    )