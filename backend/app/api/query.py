from fastapi import APIRouter
from sqlalchemy import text

from app.database.connection import engine
from app.services.ai_service import generate_sql
from app.utils.sql_validator import validate_sql

router = APIRouter()


@router.post("/query")
def query(data: dict):
    question = data["question"]

    sql = generate_sql(question)
    if not validate_sql(sql):
        return {
        "error": "Unsafe SQL generated."
    }

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.mappings().all()

    return {
        "question": question,
        "sql": sql,
        "data": rows
    }