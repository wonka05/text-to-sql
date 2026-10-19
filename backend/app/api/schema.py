from fastapi import APIRouter, Depends

from app.api.deps import Services, get_services
from app.core.errors import AppError
from app.schemas.schema import SchemaColumn, SchemaResponse, SchemaTable

router = APIRouter()


@router.get("/schema", response_model=SchemaResponse)
def get_schema(services: Services = Depends(get_services)):
    """The tables and columns the assistant knows about."""
    catalog = services.catalog.get()
    return SchemaResponse(
        database=catalog.database,
        fingerprint=catalog.fingerprint,
        loaded_at=catalog.loaded_at,
        tables=[
            SchemaTable(
                name=table.name,
                is_view=table.is_view,
                row_count=table.row_count,
                comment=table.comment,
                columns=[
                    SchemaColumn(
                        name=column.name,
                        type=column.type,
                        nullable=column.nullable,
                        primary_key=column.primary_key,
                        restricted=column.restricted,
                        references=(
                            f"{fk.ref_table}.{fk.ref_column}"
                            if (fk := table.foreign_key(column.name))
                            else None
                        ),
                        values=list(column.values) if column.values else None,
                        value_range=list(column.value_range) if column.value_range else None,
                        comment=column.comment,
                    )
                    for column in table.columns
                ],
            )
            for table in catalog.tables
        ],
    )


@router.get("/health")
def health(services: Services = Depends(get_services)):
    """Whether the database is reachable. Always 200 so the UI can show the state."""
    try:
        services.executor.ping()
        database = {"ok": True, "error": None}
    except AppError as exc:
        database = {"ok": False, "error": exc.message}
    return {
        "status": "ok" if database["ok"] else "degraded",
        "database": database,
        "model": services.pipeline.model_name,
    }
