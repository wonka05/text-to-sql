from datetime import datetime

from pydantic import BaseModel


class SchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool
    restricted: bool
    references: str | None = None
    values: list[str] | None = None
    value_range: list[str] | None = None
    comment: str | None = None


class SchemaTable(BaseModel):
    name: str
    is_view: bool
    row_count: int | None
    comment: str | None = None
    columns: list[SchemaColumn]


class SchemaResponse(BaseModel):
    database: str
    fingerprint: str
    loaded_at: datetime
    tables: list[SchemaTable]
