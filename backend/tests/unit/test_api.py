from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import Services
from app.core.config import Settings
from app.core.errors import DatabaseUnavailableError, ModelUnavailableError
from app.main import create_app
from app.services.catalog import CatalogProvider
from app.services.pipeline import QueryPipeline
from app.services.rate_limit import RateLimiter
from tests.conftest import FakeExecutor, FakeLLM, make_catalog, sql_reply

ORIGIN = "http://localhost:5173"


def make_client(llm=None, executor=None, catalog_load=make_catalog, rate_limit=0):
    executor = executor or FakeExecutor()
    catalog = CatalogProvider(catalog_load, ttl_seconds=3600)
    pipeline = QueryPipeline(
        llm=llm or FakeLLM(),
        catalog=catalog,
        executor=executor,
        max_rows=500,
        today=lambda: date(2026, 10, 19),
    )
    services = Services(pipeline, catalog, executor, RateLimiter(rate_limit))
    settings = Settings(
        _env_file=None, gemini_api_key="x", db_name="shop", db_user="u", db_password="p",
        allowed_origins=ORIGIN,
    )
    return TestClient(create_app(settings=settings, services=services), raise_server_exceptions=False)


def test_query_returns_the_answer():
    with make_client(FakeLLM(sql_reply("SELECT department_name FROM departments"))) as client:
        response = client.post("/query", json={"question": "Departments?"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["result"]["rows"] == [["Engineering", 3]]
    assert body["result"]["columns"] == [
        {"name": "department_name", "type": "text"}, {"name": "employees", "type": "number"},
    ]
    assert body["timings"]["total_ms"] >= 0


def test_query_accepts_history():
    llm = FakeLLM(sql_reply("SELECT department_name FROM departments"))
    with make_client(llm) as client:
        response = client.post("/query", json={
            "question": "And the others?",
            "history": [{"question": "Engineering staff", "sql": "SELECT 1", "reply": None}],
        })
    assert response.status_code == 200
    assert "Engineering staff" in llm.prompts[0]


def test_rejected_sql_is_a_normal_response_not_an_http_error():
    with make_client(FakeLLM(sql_reply("DELETE FROM employees"))) as client:
        response = client.post("/query", json={"question": "Delete everyone"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.parametrize("payload", [
    {}, {"question": ""}, {"question": "x" * 501}, {"question": "ok", "history": "nope"},
])
def test_invalid_requests_get_a_422_error_envelope(payload):
    with make_client() as client:
        response = client.post("/query", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_oversized_bodies_are_refused_before_parsing():
    with make_client() as client:
        response = client.post(
            "/query", content=b'{"question": "' + b"x" * 70_000 + b'"}',
            headers={"Content-Type": "application/json", "Origin": ORIGIN},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_model_outage_is_a_502():
    with make_client(FakeLLM(ModelUnavailableError("The AI model is not available right now."))) as client:
        response = client.post("/query", json={"question": "q"})
    assert response.status_code == 502
    assert response.json() == {"error": {
        "code": "model_unavailable", "message": "The AI model is not available right now."}}


def test_database_outage_is_a_503():
    def broken_catalog():
        raise DatabaseUnavailableError("The database is not reachable right now.")

    with make_client(catalog_load=broken_catalog) as client:
        response = client.post("/query", json={"question": "q"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_unexpected_errors_are_json_and_keep_cors_headers():
    with make_client(FakeLLM(RuntimeError("bug"))) as client:
        response = client.post("/query", json={"question": "q"}, headers={"Origin": ORIGIN})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "bug" not in response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_rate_limit_returns_429_with_retry_after():
    llm = FakeLLM(*[sql_reply("SELECT department_name FROM departments")] * 3)
    with make_client(llm, rate_limit=2) as client:
        codes = [client.post("/query", json={"question": f"q{i}"}).status_code for i in range(3)]
        limited = client.post("/sql", json={"sql": "SELECT 1"})
    assert codes == [200, 200, 429]
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    assert limited.json()["error"]["code"] == "rate_limited"


def test_sql_endpoint_runs_user_sql_through_the_guard():
    with make_client() as client:
        ok = client.post("/sql", json={"sql": "SELECT department_name FROM departments"})
        blocked = client.post("/sql", json={"sql": "UPDATE employees SET salary = 0"})
    assert ok.json()["status"] == "answered"
    assert blocked.status_code == 200 and blocked.json()["status"] == "rejected"


def test_schema_endpoint_describes_tables():
    with make_client() as client:
        body = client.get("/schema").json()
    employees = next(t for t in body["tables"] if t["name"] == "employees")
    dept = next(c for c in employees["columns"] if c["name"] == "department_id")
    assert dept["references"] == "departments.department_id"
    assert body["database"] == "shop" and len(body["fingerprint"]) == 12


def test_health_reports_database_state():
    class DownExecutor(FakeExecutor):
        def ping(self):
            raise DatabaseUnavailableError("The database is not reachable right now.")

    with make_client() as client:
        assert client.get("/health").json()["status"] == "ok"
    with make_client(executor=DownExecutor()) as client:
        body = client.get("/health").json()
    assert body["status"] == "degraded" and body["database"]["ok"] is False
