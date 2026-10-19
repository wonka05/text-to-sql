from fastapi import APIRouter, Depends

from app.api.deps import Services, enforce_rate_limit, get_services
from app.schemas.query import QueryRequest, QueryResponse, SqlRequest
from app.services.prompts import HistoryTurn

router = APIRouter(dependencies=[Depends(enforce_rate_limit)])


@router.post("/query", response_model=QueryResponse)
def ask_question(request: QueryRequest, services: Services = Depends(get_services)):
    """Answer a natural-language question with a generated, checked SQL query.

    Every outcome of the pipeline (answered, clarification, unsupported,
    rejected, failed) is a 200 response with a `status`. Non-200 responses
    mean the request itself could not be handled: invalid input (422), rate
    limit (429), or the model or database being unavailable (502/503).
    """
    history = [
        HistoryTurn(question=turn.question, sql=turn.sql, reply=turn.reply)
        for turn in request.history
    ]
    return services.pipeline.ask(request.question, history)


@router.post("/sql", response_model=QueryResponse)
def run_sql(request: SqlRequest, services: Services = Depends(get_services)):
    """Run SQL written or edited by the user, through the same guard as generated SQL."""
    return services.pipeline.run_sql(request.sql)
