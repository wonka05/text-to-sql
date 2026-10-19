"""The real database layer: catalog, executor, safety settings and the API."""
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.deps import Services
from app.core.errors import DatabaseUnavailableError
from app.database.connection import create_query_engine
from app.main import create_app
from app.services.catalog import CatalogProvider, load_catalog
from app.services.executor import QueryExecutionError, QueryExecutor, to_json_value
from app.services.pipeline import QueryPipeline
from app.services.rate_limit import RateLimiter
from app.services.sql_guard import CheckedQuery, GuardPolicy, check_query
from tests.conftest import FakeLLM, sql_reply

QUESTIONS = Path(__file__).resolve().parents[2] / "evals" / "questions.json"


def unchecked(sql: str) -> CheckedQuery:
    """Bypass the guard, to prove the database layers hold on their own."""
    return CheckedQuery(sql=sql, tables=(), limit_applied=False)


@pytest.fixture(scope="module")
def catalog(engine, mysql_settings):
    return load_catalog(engine, mysql_settings.db_name, frozenset({("employees", "phone")}))


@pytest.fixture(scope="module")
def executor(engine, mysql_settings):
    return QueryExecutor(engine, mysql_settings.max_result_rows, mysql_settings.query_timeout_seconds)


@pytest.fixture(scope="module")
def policy(catalog, mysql_settings):
    return GuardPolicy(
        database=catalog.database,
        schema=catalog.guard_schema(),
        restricted_columns=frozenset({("employees", "phone")}),
        max_rows=mysql_settings.max_result_rows,
    )


class TestCatalog:
    def test_reads_tables_keys_and_relationships(self, catalog):
        assert [t.name for t in catalog.tables] == [
            "customers", "departments", "employees", "order_items", "orders", "products",
        ]
        employees = catalog.table("employees")
        assert employees.row_count == 100
        assert next(c for c in employees.columns if c.name == "employee_id").primary_key
        fk = employees.foreign_key("department_id")
        assert (fk.ref_table, fk.ref_column) == ("departments", "department_id")

    def test_lists_values_of_small_text_columns(self, catalog):
        city = next(c for c in catalog.table("customers").columns if c.name == "city")
        assert len(city.values) == 10 and "Mumbai" in city.values
        category = next(c for c in catalog.table("products").columns if c.name == "category")
        assert "Home & Kitchen" in category.values

    def test_records_date_ranges(self, catalog):
        order_date = next(c for c in catalog.table("orders").columns if c.name == "order_date")
        assert order_date.value_range[1] <= "2026-09-30"

    def test_never_profiles_sensitive_or_restricted_columns(self, catalog):
        columns = {c.name: c for c in catalog.table("employees").columns}
        assert columns["email"].values is None
        assert columns["phone"].restricted and columns["phone"].values is None
        assert columns["first_name"].values is None  # too many distinct values


class TestExecutor:
    def test_returns_typed_json_values_in_column_order(self, executor, policy):
        result = executor.run(check_query(
            "SELECT first_name, salary, hire_date FROM employees ORDER BY employee_id LIMIT 1", policy))
        assert [c.name for c in result.columns] == ["first_name", "salary", "hire_date"]
        assert [c.type for c in result.columns] == ["text", "number", "date"]
        name, salary, hired = result.rows[0]
        assert isinstance(salary, int) and len(hired) == 10

    def test_duplicate_column_names_are_kept(self, executor, policy):
        result = executor.run(check_query(
            "SELECT a.first_name, b.first_name FROM employees a JOIN employees b "
            "ON a.employee_id = b.employee_id LIMIT 1", policy))
        assert [c.name for c in result.columns] == ["first_name", "first_name"]
        assert len(result.rows[0]) == 2

    def test_percent_signs_and_colons_are_sent_unchanged(self, executor, policy):
        result = executor.run(check_query(
            "SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, 'a :b' AS literal "
            "FROM orders ORDER BY order_date LIMIT 1", policy))
        month, literal = result.rows[0]
        assert len(month) == 7 and literal == "a :b"

    def test_large_results_are_cut_off_and_flagged(self, executor, policy):
        result = executor.run(check_query("SELECT order_id FROM orders", policy))
        assert result.row_count == 50 and result.truncated

    def test_small_results_are_not_flagged(self, executor, policy):
        result = executor.run(check_query("SELECT department_name FROM departments", policy))
        assert result.row_count == 8 and not result.truncated

    def test_slow_queries_hit_the_time_limit(self, executor):
        heavy = ("SELECT SUM(a.quantity * b.quantity * c.quantity) "
                 "FROM order_items a, order_items b, order_items c")
        with pytest.raises(QueryExecutionError) as info:
            executor.run(unchecked(heavy))
        assert not info.value.repairable
        assert "1 second limit" in info.value.message

    def test_unknown_columns_are_repairable_and_flag_schema_drift(self, executor):
        with pytest.raises(QueryExecutionError) as info:
            executor.run(unchecked("SELECT nickname FROM employees"))
        assert info.value.repairable and info.value.schema_changed
        assert "1054" in info.value.message

    def test_writes_fail_even_without_the_guard(self, executor):
        with pytest.raises(QueryExecutionError) as info:
            executor.run(unchecked("DELETE FROM orders"))
        assert not info.value.repairable
        # The server's message names the account; it must not reach the user
        assert "querygenie" not in info.value.message

    def test_session_is_read_only_even_for_an_admin_account(self, admin_url, mysql_settings):
        admin_settings = mysql_settings.model_copy(update={
            "db_user": admin_url.username, "db_password": admin_url.password,
        })
        admin_engine = create_query_engine(admin_settings)
        try:
            with admin_engine.connect() as conn:
                assert conn.execute(text("SELECT @@transaction_read_only")).scalar() == 1
                with pytest.raises(Exception, match="READ ONLY"):
                    conn.execute(text("UPDATE products SET price = price WHERE product_id = 1"))
        finally:
            admin_engine.dispose()

    def test_unreachable_database(self, mysql_settings):
        dead = create_query_engine(mysql_settings.model_copy(update={"db_port": 1}))
        with pytest.raises(DatabaseUnavailableError):
            QueryExecutor(dead, 10, 1).run(unchecked("SELECT 1"))
        with pytest.raises(DatabaseUnavailableError):
            load_catalog(dead, mysql_settings.db_name)
        dead.dispose()


def gold_items():
    return [i for i in json.loads(QUESTIONS.read_text(encoding="utf-8")) if i["expect"] == "sql"]


@pytest.mark.parametrize("item", gold_items(), ids=lambda i: i["id"])
def test_guard_rewrite_preserves_gold_query_results(item, engine, executor, policy, mysql_settings):
    """Every evaluation query passes the guard, and running the guard's
    re-generated SQL gives the same rows as running the original text."""
    checked = check_query(item["gold_sql"], policy)
    via_guard = executor.run(checked)
    with engine.connect() as conn:
        raw = conn.exec_driver_sql(
            item["gold_sql"], execution_options={"no_parameters": True}).fetchall()

    limit = mysql_settings.max_result_rows
    if len(raw) > limit:
        assert via_guard.truncated and via_guard.row_count == limit
    else:
        expected = sorted(map(repr, ([to_json_value(v) for v in row] for row in raw)))
        assert sorted(map(repr, via_guard.rows)) == expected


def test_api_end_to_end_with_a_scripted_model(engine, catalog, executor, mysql_settings):
    provider = CatalogProvider(lambda: catalog, ttl_seconds=3600)
    llm = FakeLLM(
        # First try uses a column that does not exist, so the pipeline repairs it
        sql_reply("SELECT department, COUNT(*) FROM employees GROUP BY department"),
        sql_reply("SELECT d.department_name, COUNT(*) AS employees FROM employees e "
                  "JOIN departments d ON e.department_id = d.department_id "
                  "GROUP BY d.department_name ORDER BY employees DESC"),
    )
    pipeline = QueryPipeline(llm, provider, executor, max_rows=mysql_settings.max_result_rows,
                             today=lambda: date(2026, 10, 19))
    services = Services(pipeline, provider, executor, RateLimiter(0))

    with TestClient(create_app(settings=mysql_settings, services=services)) as client:
        body = client.post("/query", json={"question": "Employees per department?"}).json()
        health = client.get("/health").json()
        schema = client.get("/schema").json()
        edited = client.post("/sql", json={"sql": "SELECT COUNT(*) AS n FROM customers"}).json()

    assert body["status"] == "answered"
    assert body["result"]["rows"][0] == ["Engineering", 35]
    assert sum(row[1] for row in body["result"]["rows"]) == 100
    assert body["attempts"][0]["stage"] == "validation"
    assert health == {"status": "ok", "database": {"ok": True, "error": None}, "model": "fake-model"}
    assert len(schema["tables"]) == 6
    assert edited["result"]["rows"] == [[200]]
