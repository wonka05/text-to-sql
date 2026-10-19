from datetime import date

from app.services.prompts import HistoryTurn, build_prompt, build_repair_prompt, render_schema
from tests.conftest import make_catalog


def test_schema_lists_keys_relationships_values_and_ranges():
    text = render_schema(make_catalog())
    assert "employee_id INTEGER | primary key" in text
    assert "department_id INTEGER | references departments.department_id" in text
    assert "values: 'Engineering', 'Sales'" in text
    assert "range: 2022-06-06 to 2026-09-28" in text
    assert "table employees, 10 rows" in text


def test_restricted_columns_are_hidden_from_the_model():
    text = render_schema(make_catalog(frozenset({("employees", "salary")})))
    assert "salary" not in text
    assert "first_name" in text


def test_prompt_has_date_schema_and_question_but_no_history_section_when_empty():
    prompt = build_prompt("How many orders?", make_catalog(), [], date(2026, 10, 19))
    assert "Today's date: 2026-10-19" in prompt
    assert '<schema database="shop">' in prompt
    assert "<question>\nHow many orders?\n</question>" in prompt
    assert "<conversation>" not in prompt


def test_prompt_includes_earlier_turns_in_order():
    history = [
        HistoryTurn(question="Employees per department", sql="SELECT 1"),
        HistoryTurn(question="Top ones", reply="Top by what?"),
    ]
    prompt = build_prompt("By salary", make_catalog(), history, date(2026, 10, 19))
    conversation = prompt[prompt.index("<conversation>"):prompt.index("</conversation>")]
    assert conversation.index("Employees per department") < conversation.index("Top ones")
    assert "Assistant ran: SELECT 1" in conversation
    assert "Assistant replied: Top by what?" in conversation


def test_repair_prompt_carries_the_failed_sql_and_error():
    prompt = build_repair_prompt("BASE", "SELECT nope FROM t", "Unknown column 'nope'")
    assert prompt.startswith("BASE")
    assert "SELECT nope FROM t" in prompt and "Unknown column 'nope'" in prompt
