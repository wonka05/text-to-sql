"""Measure how well the assistant answers a fixed set of questions.

Each item in questions.json either has a gold SQL query (the answer is
correct when its *results* match the gold query's results; see scoring.py)
or a list of acceptable outcomes (e.g. "clarification" for a vague question,
"unsupported" or "rejected" for "drop the customers table").

Run from the backend/ folder, against a database seeded by scripts/setup_db.py:

    python -m evals.run --gold              # check the harness and gold SQL; no model calls
    python -m evals.run                     # full run: about 1-2 model calls per question
    python -m evals.run --category join     # one category
    python -m evals.run --only join-01      # one question (repeatable)

A full run calls the configured Gemini model for every question, which uses
API quota and may cost money. A JSON report is written to evals/reports/.
"""
import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.connection import create_query_engine
from app.services.catalog import CatalogProvider, load_catalog
from app.services.executor import QueryExecutor
from app.services.llm import GeminiClient
from app.services.pipeline import QueryPipeline
from app.services.prompts import HistoryTurn
from app.services.sql_guard import GuardPolicy, check_query
from evals.scoring import results_match

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "questions.json"
REPORTS_DIR = EVAL_DIR / "reports"


class CountingLLM:
    """Wraps a model client to count calls."""

    def __init__(self, inner):
        self._inner = inner
        self.model_name = inner.model_name
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self._inner.generate(system_prompt, user_prompt)


class GoldLLM:
    """Stands in for the model and answers with the expected reply.

    Used by --gold to check that every gold query passes the guard, runs, and
    is scored as a match against itself, without spending model calls.
    """

    model_name = "gold"

    def __init__(self):
        self.item = None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        expect = self.item["expect"]
        if expect == "sql":
            return json.dumps({"kind": "sql", "sql": self.item["gold_sql"]})
        kind = "unsupported" if "unsupported" in expect or "rejected" in expect else expect[0]
        if kind == "sql":
            return json.dumps({"kind": "sql", "sql": "SELECT COUNT(*) FROM orders"})
        return json.dumps({
            "kind": kind,
            "explanation": "gold",
            "clarification_question": "Which one?" if kind == "clarification" else "",
        })


def load_questions(categories: list[str], only: list[str]) -> list[dict]:
    items = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if categories:
        items = [i for i in items if i["category"] in categories]
    if only:
        items = [i for i in items if i["id"] in only]
    return items


def score_item(item, response, executor, policy) -> tuple[bool, str]:
    status = response.status
    expect = item["expect"]

    if expect != "sql":
        allowed = ["answered" if e == "sql" else e for e in expect]
        return status in allowed, f"status {status}, expected one of {allowed}"

    if status in item.get("accept_also", []):
        return True, f"accepted status {status}"
    if status != "answered":
        return False, f"status {status}: {response.message}"
    if item.get("expect_truncated"):
        ok = response.result.truncated
        return ok, "truncated as expected" if ok else "expected the row cap to apply"

    gold = executor.run(check_query(item["gold_sql"], policy))
    return results_match(
        [c.name for c in gold.columns],
        gold.rows,
        response.result.rows,
        order_matters=item.get("order_matters", False),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--gold", action="store_true", help="answer with the gold SQL (no model calls)")
    parser.add_argument(
        "--category", action="append", default=[], help="only this category (repeatable)")
    parser.add_argument(
        "--only", action="append", default=[], help="only this question id (repeatable)")
    args = parser.parse_args()

    settings = get_settings()
    items = load_questions(args.category, args.only)
    if not items:
        sys.exit("No questions selected.")

    engine = create_query_engine(settings)
    restricted = settings.restricted_column_set
    catalog = CatalogProvider(
        lambda: load_catalog(engine, settings.db_name, restricted), ttl_seconds=3600
    )
    executor = QueryExecutor(engine, settings.max_result_rows, settings.query_timeout_seconds)
    gold_llm = GoldLLM()
    if args.gold:
        llm = CountingLLM(gold_llm)
    else:
        llm = CountingLLM(GeminiClient(
            settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds))
    pipeline = QueryPipeline(
        llm=llm,
        catalog=catalog,
        executor=executor,
        max_rows=settings.max_result_rows,
        restricted_columns=restricted,
        max_repair_attempts=settings.max_repair_attempts,
    )
    current = catalog.get()
    policy = GuardPolicy(
        database=current.database,
        schema=current.guard_schema(),
        restricted_columns=restricted,
        max_rows=settings.max_result_rows,
    )

    mode = "gold answers" if args.gold else f"model {llm.model_name}"
    print(f"Evaluating {len(items)} questions with {mode} on database '{settings.db_name}'\n")

    results = []
    for item in items:
        gold_llm.item = item
        history = [HistoryTurn(**turn) for turn in item.get("history", [])]
        calls_before = llm.calls
        started = time.perf_counter()
        try:
            response = pipeline.ask(item["question"], history)
            passed, detail = score_item(item, response, executor, policy)
            status, sql, repairs = response.status, response.sql, len(response.attempts)
        except AppError as exc:
            passed, detail = False, f"{exc.code}: {exc.message}"
            status, sql, repairs = "error", None, 0
        seconds = time.perf_counter() - started

        results.append({
            "id": item["id"],
            "category": item["category"],
            "question": item["question"],
            "passed": passed,
            "status": status,
            "detail": detail,
            "sql": sql,
            "failed_attempts": repairs,
            "model_calls": llm.calls - calls_before,
            "seconds": round(seconds, 2),
        })
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  {item['id']:<16} {status:<13} {detail}")

    summary = summarize(results)
    print_summary(summary)

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{'gold' if args.gold else llm.model_name}.json"
    report = {
        "model": llm.model_name,
        "database": settings.db_name,
        "summary": summary,
        "results": results,
    }
    (REPORTS_DIR / name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to evals/reports/{name}")
    engine.dispose()


def summarize(results: list[dict]) -> dict:
    by_category = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r["passed"])

    sql_items = [r for r in results if r["category"] not in {
        "ambiguous", "unsupported", "destructive", "injection"}]
    answered = [r for r in sql_items if r["status"] == "answered"]
    return {
        "total": len(results),
        "passed": sum(r["passed"] for r in results),
        "accuracy": round(sum(r["passed"] for r in results) / len(results), 3),
        "by_category": {
            cat: f"{sum(v)}/{len(v)}" for cat, v in sorted(by_category.items())
        },
        # Of the questions that should produce a query: how many ran, and how
        # many of those that ran gave the wrong answer anyway
        "answerable_questions": len(sql_items),
        "executed": len(answered),
        "executed_but_wrong": sum(not r["passed"] for r in answered),
        "repaired_successfully": sum(r["failed_attempts"] > 0 and r["passed"] for r in results),
        "model_calls": sum(r["model_calls"] for r in results),
        "median_seconds": round(statistics.median(r["seconds"] for r in results), 2),
    }


def print_summary(summary: dict) -> None:
    print(f"\nAccuracy: {summary['passed']}/{summary['total']} ({summary['accuracy']:.1%})")
    for category, score in summary["by_category"].items():
        print(f"  {category:<14} {score}")
    print(
        f"Answerable questions: {summary['answerable_questions']}, executed: "
        f"{summary['executed']}, executed but wrong: {summary['executed_but_wrong']}"
    )
    print(
        f"Repaired successfully: {summary['repaired_successfully']}, model calls: "
        f"{summary['model_calls']}, median time: {summary['median_seconds']}s"
    )


if __name__ == "__main__":
    main()
