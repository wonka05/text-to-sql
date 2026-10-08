from fastapi import APIRouter
from sqlalchemy import text
import time

from app.core.config import settings
from app.database.connection import engine
from app.services.ai_service import generate_sql
from app.utils.sql_validator import validate_sql
from app.schemas.query import QueryRequest

router = APIRouter()


@router.post("/query")
def query(request: QueryRequest):
    question = request.question

    # Start timer
    start_time = time.perf_counter()

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

    # End timer
    end_time = time.perf_counter()

    execution_time = round((end_time - start_time) * 1000, 2)

    return {
        "question": question,
        "sql": sql,
        "explanation": explanation,
        "data": rows,
        "execution_time": execution_time,
        "rows_returned": len(rows),
        "model": settings.gemini_model,
        "status": "Success"
    }