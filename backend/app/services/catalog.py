"""Discover the database schema at runtime.

The model can only write correct SQL for tables it knows about, so instead of
a hand-written schema in the prompt the app reads the live one: tables,
columns, primary and foreign keys, plus a few facts about the data (the
distinct values of small text columns, the range of dates and numbers). Those
facts stop the model guessing filter values ("electronics" vs "Electronics")
and tell it which dates the data covers.

The catalog is cached and rebuilt every SCHEMA_CACHE_SECONDS, or sooner when
the database reports a table or column the catalog thought existed.
"""
import hashlib
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy import types as sqltypes
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import DatabaseUnavailableError
from app.database.errors import describe, is_connection_error

logger = logging.getLogger(__name__)

# Bigger tables are not profiled, so building the catalog stays fast
PROFILE_MAX_ROWS = 200_000
# Text columns with at most this many distinct values get them listed
MAX_LISTED_VALUES = 20
MAX_VALUE_LENGTH = 60
# Values of columns with names like these are never read or sent to the model
SENSITIVE_NAME = re.compile(
    r"mail|phone|mobile|passw|secret|token|ssn|address|salt|hash|iban|card",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    kind: str  # "number", "text", "date" or "other"
    nullable: bool = True
    primary_key: bool = False
    restricted: bool = False
    comment: str | None = None
    # All distinct values, when there are only a few
    values: tuple[str, ...] | None = None
    # (min, max) for dates and numbers
    value_range: tuple[str, str] | None = None


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: tuple[ColumnInfo, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    row_count: int | None = None
    is_view: bool = False
    comment: str | None = None

    def foreign_key(self, column: str) -> ForeignKey | None:
        for fk in self.foreign_keys:
            if fk.column == column:
                return fk
        return None


@dataclass(frozen=True)
class Catalog:
    database: str
    tables: tuple[TableInfo, ...]
    loaded_at: datetime = field(default_factory=datetime.now)

    @property
    def fingerprint(self) -> str:
        """Changes whenever a table, column or type changes."""
        parts = [
            f"{t.name}.{c.name}:{c.type}:{c.restricted}"
            for t in self.tables
            for c in t.columns
        ]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:12]

    def table(self, name: str) -> TableInfo | None:
        name = name.lower()
        for table in self.tables:
            if table.name.lower() == name:
                return table
        return None

    def guard_schema(self) -> dict[str, dict[str, str]]:
        """Lower-cased {table: {column: type}} mapping for the SQL guard.

        Restricted columns stay in, so `SELECT *` expands to include them and
        is rejected instead of silently reading them.
        """
        simple_type = {"number": "DOUBLE", "date": "DATETIME"}
        return {
            t.name.lower(): {
                c.name.lower(): simple_type.get(c.kind, "TEXT") for c in t.columns
            }
            for t in self.tables
        }


def column_kind(sa_type: sqltypes.TypeEngine) -> str:
    if isinstance(sa_type, (sqltypes.Integer, sqltypes.Numeric)):
        return "number"
    if isinstance(sa_type, (sqltypes.Date, sqltypes.DateTime)):
        return "date"
    if isinstance(sa_type, sqltypes.String):
        return "text"
    return "other"


def _type_name(sa_type: sqltypes.TypeEngine) -> str:
    # Reflected MySQL types carry collation details the model doesn't need
    name = str(sa_type)
    return re.sub(r"\s+(COLLATE|CHARACTER SET)\s+\S+", "", name).strip()


def _format_value(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def load_catalog(
    engine: Engine,
    database: str,
    restricted: frozenset[tuple[str, str]] = frozenset(),
) -> Catalog:
    try:
        with engine.connect() as conn:
            return _read_catalog(conn, database, restricted)
    except SQLAlchemyError as exc:
        if is_connection_error(exc):
            logger.error("Could not load the schema: %s", describe(exc))
            raise DatabaseUnavailableError(
                "The database is not reachable right now."
            ) from exc
        raise


def _read_catalog(
    conn: Connection,
    database: str,
    restricted: frozenset[tuple[str, str]],
) -> Catalog:
    inspector = inspect(conn)
    view_names = set(inspector.get_view_names())
    names = sorted(set(inspector.get_table_names()) | view_names)

    estimates = dict(
        conn.execute(
            text(
                "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()
    )

    tables = []
    for name in names:
        is_view = name in view_names
        pk_columns = set()
        foreign_keys = []
        if not is_view:
            pk_columns = set(inspector.get_pk_constraint(name).get("constrained_columns") or [])
            for fk in inspector.get_foreign_keys(name):
                pairs = zip(fk["constrained_columns"], fk["referred_columns"], strict=True)
                for col, ref_col in pairs:
                    foreign_keys.append(ForeignKey(col, fk["referred_table"], ref_col))

        columns = [
            ColumnInfo(
                name=col["name"],
                type=_type_name(col["type"]),
                kind=column_kind(col["type"]),
                nullable=bool(col.get("nullable", True)),
                primary_key=col["name"] in pk_columns,
                restricted=(name.lower(), col["name"].lower()) in restricted,
                comment=col.get("comment") or None,
            )
            for col in inspector.get_columns(name)
        ]

        row_count = _count_rows(conn, name, estimates.get(name))
        if row_count is not None and row_count <= PROFILE_MAX_ROWS:
            fk_columns = {fk.column for fk in foreign_keys}
            columns = _profile(conn, name, columns, fk_columns)

        comment = None
        if not is_view:
            comment = inspector.get_table_comment(name).get("text") or None

        tables.append(TableInfo(
            name=name,
            columns=tuple(columns),
            foreign_keys=tuple(foreign_keys),
            row_count=row_count,
            is_view=is_view,
            comment=comment,
        ))

    return Catalog(database=database, tables=tuple(tables))


def _quote(conn: Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _count_rows(conn: Connection, table: str, estimate) -> int | None:
    # information_schema's estimate is instant but can be stale; count exactly
    # unless the table is clearly too big for that to be cheap
    if estimate is not None and estimate > PROFILE_MAX_ROWS:
        return int(estimate)
    try:
        return conn.execute(text(f"SELECT COUNT(*) FROM {_quote(conn, table)}")).scalar()
    except SQLAlchemyError as exc:
        if is_connection_error(exc):
            raise
        logger.warning("Could not count rows in %s: %s", table, exc)
        return None


def _profileable(column: ColumnInfo, fk_columns: set[str]) -> bool:
    return not (
        column.restricted
        or column.primary_key
        or column.name in fk_columns
        or SENSITIVE_NAME.search(column.name)
    )


def _profile(
    conn: Connection,
    table: str,
    columns: list[ColumnInfo],
    fk_columns: set[str],
) -> list[ColumnInfo]:
    """Add value lists and ranges. A failure only skips that column."""
    quoted_table = _quote(conn, table)
    profiled = []
    for column in columns:
        if not _profileable(column, fk_columns):
            profiled.append(column)
            continue

        quoted = _quote(conn, column.name)
        try:
            if column.kind in ("number", "date"):
                low, high = conn.execute(
                    text(f"SELECT MIN({quoted}), MAX({quoted}) FROM {quoted_table}")
                ).one()
                if low is not None:
                    column = replace(column, value_range=(_format_value(low), _format_value(high)))
            elif column.kind == "text":
                values = conn.execute(text(
                    f"SELECT DISTINCT {quoted} FROM {quoted_table} "
                    f"WHERE {quoted} IS NOT NULL ORDER BY {quoted} "
                    f"LIMIT {MAX_LISTED_VALUES + 1}"
                )).scalars().all()
                listable = [str(v) for v in values]
                if (
                    0 < len(listable) <= MAX_LISTED_VALUES
                    and all(len(v) <= MAX_VALUE_LENGTH and "\n" not in v for v in listable)
                ):
                    column = replace(column, values=tuple(listable))
        except SQLAlchemyError as exc:
            if is_connection_error(exc):
                raise
            logger.warning("Could not profile %s.%s: %s", table, column.name, exc)
        profiled.append(column)
    return profiled


class CatalogProvider:
    """Thread-safe cache around a catalog loader."""

    def __init__(
        self,
        load: Callable[[], Catalog],
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._load = load
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._catalog: Catalog | None = None
        self._loaded_at = 0.0

    def get(self) -> Catalog:
        with self._lock:
            stale = self._clock() - self._loaded_at >= self._ttl
            if self._catalog is None or stale:
                self._catalog = self._load()
                self._loaded_at = self._clock()
                logger.info(
                    "Loaded schema catalog: %d tables, fingerprint %s",
                    len(self._catalog.tables),
                    self._catalog.fingerprint,
                )
            return self._catalog

    def invalidate(self) -> None:
        with self._lock:
            self._catalog = None
