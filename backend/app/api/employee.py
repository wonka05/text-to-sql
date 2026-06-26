from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.employee_service import get_all_employees

router = APIRouter()


@router.get("/employees")
def employees(db: Session = Depends(get_db)):
    return get_all_employees(db)