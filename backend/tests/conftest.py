"""Shared test setup.

Unit tests never touch a real database or model: they use the fakes below.
Tests against MySQL live in tests/integration and are skipped unless
QG_TEST_MYSQL_ADMIN_URL is set.
"""
import json
import os

# app.main builds a module-level app at import, which reads settings. Give it
# harmless values so tests never pick up real credentials from backend/.env.
os.environ.update({
    "GEMINI_API_KEY": "test-key-not-used",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "1",
    "DB_NAME": "unit_test",
    "DB_USER": "unit_test",
    "DB_PASSWORD": "unit-test-password",
})

import pytest  # noqa: E402

from app.services.catalog import Catalog, CatalogProvider, ColumnInfo, ForeignKey, TableInfo  # noqa: E402
from app.services.executor import Column, QueryExecutionError, ResultSet  # noqa: E402


def col(name, kind="number", **extra) -> ColumnInfo:
    types = {"number": "INTEGER", "text": "VARCHAR(100)", "date": "DATE"}
    return ColumnInfo(name=name, type=types.get(kind, "TEXT"), kind=kind, **extra)


def make_catalog(restricted=frozenset()) -> Catalog:
    """A small version of the sample schema."""

    def c(table, name, kind="number", **extra):
        return col(name, kind, restricted=(table, name) in restricted, **extra)

    return Catalog(
        database="shop",
        tables=(
            TableInfo(
                name="departments",
                row_count=3,
                columns=(
                    c("departments", "department_id", primary_key=True),
                    c("departments", "department_name", "text", values=("Engineering", "Sales")),
                ),
            ),
            TableInfo(
                name="employees",
                row_count=10,
                columns=(
                    c("employees", "employee_id", primary_key=True),
                    c("employees", "first_name", "text"),
                    c("employees", "last_name", "text"),
                    c("employees", "email", "text"),
                    c("employees", "salary", value_range=("40000.00", "177000.00")),
                    c("employees", "hire_date", "date"),
                    c("employees", "department_id"),
                ),
                foreign_keys=(ForeignKey("department_id", "departments", "department_id"),),
            ),
            TableInfo(
                name="orders",
                row_count=5,
                columns=(
                    c("orders", "order_id", primary_key=True),
                    c("orders", "order_date", "date", value_range=("2022-06-06", "2026-09-28")),
                    c("orders", "total_amount"),
                ),
            ),
        ),
    )


class FakeLLM:
    """Returns scripted replies in order and records every prompt."""

    model_name = "fake-model"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append(user_prompt)
        if not self.replies:
            raise AssertionError("FakeLLM ran out of scripted replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


def sql_reply(sql, explanation="Does the thing.", assumptions=()):
    return {"kind": "sql", "sql": sql, "explanation": explanation,
            "assumptions": list(assumptions), "clarification_question": "", "options": []}


class FakeExecutor:
    """Returns a fixed result, or raises scripted errors first. Records SQL."""

    def __init__(self, *errors, rows=None):
        self.errors = list(errors)
        self.rows = rows if rows is not None else [["Engineering", 3]]
        self.executed: list[str] = []

    def run(self, query):
        self.executed.append(query.sql)
        if self.errors:
            raise self.errors.pop(0)
        return ResultSet(
            columns=[Column("department_name", "text"), Column("employees", "number")],
            rows=self.rows,
            truncated=False,
            row_limit=500,
            duration_ms=1.0,
        )

    def ping(self):
        return None


def execution_error(message="Unknown column 'x'", repairable=True, schema_changed=False):
    return QueryExecutionError(message, repairable=repairable, schema_changed=schema_changed)


@pytest.fixture
def catalog():
    return make_catalog()


@pytest.fixture
def catalog_provider(catalog):
    return CatalogProvider(lambda: catalog, ttl_seconds=3600)
