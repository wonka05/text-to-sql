from datetime import date

import pytest

from app.core.errors import ModelOutputError, ModelUnavailableError
from app.services.catalog import CatalogProvider
from app.services.pipeline import QueryPipeline, ReplyCache
from app.services.prompts import HistoryTurn
from tests.conftest import FakeExecutor, FakeLLM, execution_error, make_catalog, sql_reply

GOOD_SQL = (
    "SELECT d.department_name, COUNT(*) AS employees FROM employees e "
    "JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name"
)


def pipeline(llm, executor=None, catalog_provider=None, **kwargs):
    provider = catalog_provider or CatalogProvider(make_catalog, ttl_seconds=3600)
    return QueryPipeline(
        llm=llm,
        catalog=provider,
        executor=executor or FakeExecutor(),
        max_rows=500,
        today=lambda: date(2026, 10, 19),
        **kwargs,
    )


def test_answers_with_results_and_both_sql_versions():
    llm = FakeLLM(sql_reply(GOOD_SQL, "Counts employees per department.", ["All departments"]))
    response = pipeline(llm).ask("How many employees per department?", [])

    assert response.status == "answered"
    assert response.sql == GOOD_SQL
    assert response.executed_sql.endswith("LIMIT 501")
    assert response.explanation == "Counts employees per department."
    assert response.assumptions == ["All departments"]
    assert response.result.rows == [["Engineering", 3]]
    assert response.result.columns[0].name == "department_name"
    assert response.attempts == []
    assert response.model == "fake-model"


def test_clarification_is_passed_through_without_running_sql():
    executor = FakeExecutor()
    llm = FakeLLM({"kind": "clarification", "clarification_question": "Top by what?",
                   "options": ["Top by salary", "Top by tenure"]})
    response = pipeline(llm, executor).ask("Show the top ones", [])

    assert response.status == "clarification"
    assert response.message == "Top by what?"
    assert response.options == ["Top by salary", "Top by tenure"]
    assert response.sql is None and executor.executed == []


def test_unsupported_explains_why():
    llm = FakeLLM({"kind": "unsupported", "explanation": "There is no weather data."})
    response = pipeline(llm).ask("Weather?", [])
    assert response.status == "unsupported"
    assert response.message == "There is no weather data."


def test_repairs_a_query_the_guard_rejected():
    llm = FakeLLM(sql_reply("SELECT nickname FROM employees"), sql_reply(GOOD_SQL))
    response = pipeline(llm, max_repair_attempts=1).ask("Employees per department", [])

    assert response.status == "answered"
    assert response.sql == GOOD_SQL
    [attempt] = response.attempts
    assert attempt.stage == "validation" and attempt.sql == "SELECT nickname FROM employees"
    # The repair prompt showed the model its mistake and the reason
    assert "SELECT nickname FROM employees" in llm.prompts[1]
    assert "nickname" in llm.prompts[1] and "could not be resolved" in llm.prompts[1]


def test_repairs_a_query_the_database_rejected():
    executor = FakeExecutor(execution_error("MySQL error 1064: syntax error near 'FROMM'"))
    llm = FakeLLM(sql_reply(GOOD_SQL), sql_reply(GOOD_SQL + " ORDER BY employees DESC"))
    response = pipeline(llm, executor, max_repair_attempts=1).ask("q", [])

    assert response.status == "answered"
    assert response.attempts[0].stage == "execution"
    assert "1064" in llm.prompts[1]
    assert len(executor.executed) == 2


def test_repaired_query_goes_through_the_guard_again():
    # The "fix" is a write; it must be rejected, not executed
    executor = FakeExecutor(execution_error())
    llm = FakeLLM(sql_reply(GOOD_SQL), sql_reply("DELETE FROM employees"))
    response = pipeline(llm, executor, max_repair_attempts=1).ask("q", [])

    assert response.status == "rejected"
    assert response.sql == "DELETE FROM employees"
    assert len(executor.executed) == 1


def test_write_statements_are_rejected_without_asking_for_a_repair():
    llm = FakeLLM(sql_reply("DROP TABLE employees"))
    response = pipeline(llm, max_repair_attempts=2).ask("Drop the table", [])

    assert response.status == "rejected"
    assert "read-only SELECT" in response.message
    assert len(llm.prompts) == 1


def test_timeouts_are_not_repaired():
    executor = FakeExecutor(execution_error("The query ran longer than 5 seconds", repairable=False))
    llm = FakeLLM(sql_reply(GOOD_SQL))
    response = pipeline(llm, executor, max_repair_attempts=2).ask("q", [])

    assert response.status == "failed"
    assert "longer than" in response.message
    assert len(llm.prompts) == 1


def test_gives_up_after_the_repair_budget():
    llm = FakeLLM(sql_reply("SELECT a FROM employees"), sql_reply("SELECT b FROM employees"))
    response = pipeline(llm, max_repair_attempts=1).ask("q", [])

    assert response.status == "rejected"
    assert response.sql == "SELECT b FROM employees"
    assert [a.sql for a in response.attempts] == ["SELECT a FROM employees"]
    assert len(llm.prompts) == 2


def test_no_repairs_when_disabled():
    llm = FakeLLM(sql_reply("SELECT a FROM employees"))
    response = pipeline(llm, max_repair_attempts=0).ask("q", [])
    assert response.status == "rejected" and len(llm.prompts) == 1


def test_malformed_model_output_is_retried_once():
    llm = FakeLLM("this is not json", sql_reply(GOOD_SQL))
    response = pipeline(llm, max_repair_attempts=1).ask("q", [])

    assert response.status == "answered"
    assert response.attempts[0].stage == "model_output"
    assert "not valid JSON" in llm.prompts[1]


def test_persistently_malformed_output_is_a_model_error():
    llm = FakeLLM("nope", "still nope")
    with pytest.raises(ModelOutputError):
        pipeline(llm, max_repair_attempts=1).ask("q", [])


def test_model_outage_propagates():
    llm = FakeLLM(ModelUnavailableError("down"))
    with pytest.raises(ModelUnavailableError):
        pipeline(llm).ask("q", [])


def test_schema_change_reloads_the_catalog_before_repairing():
    loads = []

    def load():
        loads.append(1)
        return make_catalog()

    provider = CatalogProvider(load, ttl_seconds=3600)
    executor = FakeExecutor(execution_error("Unknown column 'x'", schema_changed=True))
    llm = FakeLLM(sql_reply(GOOD_SQL), sql_reply(GOOD_SQL))
    pipeline(llm, executor, catalog_provider=provider, max_repair_attempts=1).ask("q", [])

    assert len(loads) == 2


class TestCache:
    def test_same_question_reuses_the_reply_but_runs_the_query_again(self):
        executor = FakeExecutor()
        llm = FakeLLM(sql_reply(GOOD_SQL))
        p = pipeline(llm, executor, cache=ReplyCache(10))

        first = p.ask("Employees per department", [])
        second = p.ask("  employees per   DEPARTMENT ", [])

        assert not first.cached and second.cached
        assert len(llm.prompts) == 1
        assert len(executor.executed) == 2

    def test_different_history_is_a_different_question(self):
        llm = FakeLLM(sql_reply(GOOD_SQL), sql_reply(GOOD_SQL))
        p = pipeline(llm, cache=ReplyCache(10))
        p.ask("And in 2024?", [HistoryTurn("Revenue in 2025", "SELECT 1")])
        p.ask("And in 2024?", [HistoryTurn("Orders in 2025", "SELECT 2")])
        assert len(llm.prompts) == 2

    def test_failed_answers_are_not_cached(self):
        llm = FakeLLM(sql_reply("DROP TABLE employees"), sql_reply("DROP TABLE employees"))
        p = pipeline(llm, cache=ReplyCache(10))
        p.ask("Drop it", [])
        p.ask("Drop it", [])
        assert len(llm.prompts) == 2

    def test_evicts_least_recently_used(self):
        cache = ReplyCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        assert cache.get("b") is None and cache.get("a") == 1


def test_only_recent_history_is_sent():
    history = [HistoryTurn(f"question {i}", f"SELECT {i}") for i in range(6)]
    llm = FakeLLM(sql_reply(GOOD_SQL))
    pipeline(llm, max_history_turns=2).ask("next", history)

    assert "question 3" not in llm.prompts[0]
    assert "question 4" in llm.prompts[0] and "question 5" in llm.prompts[0]


def test_run_sql_uses_the_guard_and_no_model():
    llm = FakeLLM()
    p = pipeline(llm)

    ok = p.run_sql("SELECT department_name FROM departments")
    assert ok.status == "answered" and ok.model is None

    blocked = p.run_sql("SELECT SLEEP(10)")
    assert blocked.status == "rejected" and "SLEEP" in blocked.message
    assert llm.prompts == []


def test_run_sql_reports_database_errors():
    p = pipeline(FakeLLM(), FakeExecutor(execution_error("MySQL error 1064: bad")))
    response = p.run_sql("SELECT department_name FROM departments")
    assert response.status == "failed" and "1064" in response.message
