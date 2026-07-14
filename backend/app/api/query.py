from fastapi import APIRouter
from sqlalchemy import text

from app.database.connection import engine
from app.services.ai_service import generate_sql
from app.utils.sql_validator import validate_sql
from app.schemas.query import QueryRequest

router = APIRouter()


@router.post("/query")
def query(request: QueryRequest):
    question = request.question

    ai_response = generate_sql(question)

    sql = ai_response["sql"]
    explanation = ai_response["explanation"]

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
        "explanation": explanation,
        "data": rows
    }