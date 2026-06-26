from sqlalchemy.orm import Session
from app.models.employee import Employee


def get_all_employees(db: Session):
    return db.query(Employee).all()