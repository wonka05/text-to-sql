"""Run a checked query and turn the rows into JSON-friendly values."""
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as time_of_day
from decimal import Decimal
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import DatabaseUnavailableError
from app.database import errors as db_errors
from app.services.sql_guard import CheckedQuery

logger = logging.getLogger(__name__)


class QueryExecutionError(Exception):
    """The database refused or aborted the query.

    `repairable`: the model may be able to fix it (e.g. a wrong column name).
    `schema_changed`: the database says a table or column is missing that
    the catalog has, so the cached catalog is out of date.
    """

    def __init__(self, message: str, repairable: bool, schema_changed: bool = False):
        super().__init__(message)
        self.message = message
        self.repairable = repairable
        self.schema_changed = schema_changed


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # "number", "text", "date", "datetime", "boolean" or "other"


@dataclass(frozen=True)
class ResultSet:
    columns: list[Column]
    rows: list[list[Any]]
    truncated: bool
    row_limit: int
    duration_ms: float

    @property
    def row_count(self) -> int:
        return len(self.rows)


class QueryExecutor:
    def __init__(self, engine: Engine, max_rows: int, timeout_seconds: float):
        self._engine = engine
        self._max_rows = max_rows
        self._timeout_seconds = timeout_seconds

    def run(self, query: CheckedQuery) -> ResultSet:
        started = time.perf_counter()
        try:
            with self._engine.connect() as conn:
                # exec_driver_sql + no_parameters sends the text as-is, so
                # "%" in DATE_FORMAT or LIKE and ":name" inside string
                # literals are not mistaken for bind parameters
                result = conn.exec_driver_sql(
                    query.sql, execution_options={"no_parameters": True}
                )
                names = list(result.keys())
                raw_rows = result.fetchmany(self._max_rows + 1)
        except SQLAlchemyError as exc:
            raise self._translate(exc) from exc

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        truncated = len(raw_rows) > self._max_rows
        rows = [[to_json_value(v) for v in row] for row in raw_rows[: self._max_rows]]
        columns = [
            Column(name=name, type=infer_type(row[i] for row in raw_rows))
            for i, name in enumerate(names)
        ]
        return ResultSet(
            columns=columns,
            rows=rows,
            truncated=truncated,
            row_limit=self._max_rows,
            duration_ms=duration_ms,
        )

    def ping(self) -> None:
        try:
            with self._engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except SQLAlchemyError as exc:
            logger.error("Database health check failed: %s", db_errors.describe(exc))
            raise DatabaseUnavailableError("The database is not reachable right now.") from exc

    def _translate(self, exc: SQLAlchemyError) -> Exception:
        code = db_errors.mysql_error_code(exc)
        if db_errors.is_connection_error(exc):
            logger.error("Database unavailable: %s", db_errors.describe(exc))
            return DatabaseUnavailableError("The database is not reachable right now.")
        if code == db_errors.QUERY_TIMEOUT:
            return QueryExecutionError(
                f"The query ran longer than the {self._timeout_seconds:g} second limit and was "
                "stopped. Try a narrower question.",
                repairable=False,
            )
        if code in db_errors.PERMISSION_ERROR_CODES:
            # The server's message names the database account; don't show it
            logger.warning("Permission denied for generated query: %s", exc)
            return QueryExecutionError(
                "The query needs access the app's read-only database account does not have.",
                repairable=False,
            )
        message = db_errors.mysql_error_message(exc)
        return QueryExecutionError(
            f"MySQL error {code}: {message}" if code else message,
            repairable=True,
            schema_changed=code in db_errors.UNKNOWN_OBJECT_CODES,
        )


def to_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        # Integers stay exact; other decimals become floats for the browser
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time_of_day)):
        return value.isoformat()
    if isinstance(value, timedelta):
        # MySQL TIME values arrive as timedelta
        total = int(value.total_seconds())
        sign = "-" if total < 0 else ""
        hours, rest = divmod(abs(total), 3600)
        return f"{sign}{hours:02d}:{rest // 60:02d}:{rest % 60:02d}"
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    return str(value)


def infer_type(values) -> str:
    """Column type for the frontend, from the Python values the driver returned."""
    kinds = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            kinds.add("boolean")
        elif isinstance(value, (int, float, Decimal)):
            kinds.add("number")
        elif isinstance(value, datetime):
            kinds.add("datetime")
        elif isinstance(value, date):
            kinds.add("date")
        elif isinstance(value, str):
            kinds.add("text")
        else:
            kinds.add("other")
    if len(kinds) == 1:
        return kinds.pop()
    return "text" if not kinds or "text" in kinds else "other"
