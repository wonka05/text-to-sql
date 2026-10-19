"""The question-to-answer pipeline.

    question ─► prompt (live schema + conversation) ─► model ─► parse JSON reply
        │                                                          │
        │            clarification / unsupported ◄─────────────────┤
        │                                                          ▼
        │                                         SQL guard ─► execute (read-only)
        │                                             │              │
        └────── repair prompt (with the error) ◄──────┴── failure ───┘

Failures that the model might fix (an unknown column, a MySQL syntax error)
are sent back to it, up to MAX_REPAIR_ATTEMPTS times. A repaired query goes
through exactly the same guard as the first one. Failures it cannot fix
(a write statement, a timeout) end the request with status "rejected" or
"failed". The response always reports what actually happened, including the
failed attempts.
"""
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from contextlib import contextmanager
from datetime import date

from app.core.errors import ModelOutputError
from app.schemas.query import (
    Attempt,
    QueryResponse,
    ResultColumn,
    ResultSetOut,
    Status,
    Timings,
)
from app.services.catalog import Catalog, CatalogProvider
from app.services.executor import QueryExecutionError, QueryExecutor, ResultSet
from app.services.llm import LLMClient, ModelReply, parse_reply
from app.services.prompts import (
    SYSTEM_PROMPT,
    HistoryTurn,
    build_format_retry_prompt,
    build_prompt,
    build_repair_prompt,
)
from app.services.sql_guard import CheckedQuery, GuardPolicy, QueryRejected, check_query

logger = logging.getLogger(__name__)


class ReplyCache:
    """Small LRU cache of model replies.

    Asking the same question against the same schema and model reuses the
    earlier reply instead of paying for another model call. The query itself
    still goes through the guard and runs again, so results are always fresh.
    """

    def __init__(self, max_size: int):
        self._max_size = max_size
        self._items: OrderedDict[Hashable, ModelReply] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> ModelReply | None:
        with self._lock:
            reply = self._items.get(key)
            if reply is not None:
                self._items.move_to_end(key)
            return reply

    def put(self, key: Hashable, reply: ModelReply) -> None:
        if self._max_size == 0:
            return
        with self._lock:
            self._items[key] = reply
            self._items.move_to_end(key)
            while len(self._items) > self._max_size:
                self._items.popitem(last=False)

    def discard(self, key: Hashable) -> None:
        with self._lock:
            self._items.pop(key, None)


class _Timer:
    def __init__(self):
        self.started = time.perf_counter()
        self.generation_ms = 0.0
        self.execution_ms = 0.0

    @contextmanager
    def generation(self):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.generation_ms += (time.perf_counter() - start) * 1000

    def timings(self) -> Timings:
        total = (time.perf_counter() - self.started) * 1000
        return Timings(
            generation_ms=round(self.generation_ms, 1),
            execution_ms=round(self.execution_ms, 1),
            total_ms=round(total, 1),
        )


class QueryPipeline:
    def __init__(
        self,
        llm: LLMClient,
        catalog: CatalogProvider,
        executor: QueryExecutor,
        max_rows: int,
        restricted_columns: frozenset[tuple[str, str]] = frozenset(),
        max_repair_attempts: int = 1,
        max_history_turns: int = 4,
        cache: ReplyCache | None = None,
        today: Callable[[], date] = date.today,
    ):
        self._llm = llm
        self._catalog = catalog
        self._executor = executor
        self._max_rows = max_rows
        self._restricted = restricted_columns
        self._max_repairs = max_repair_attempts
        self._max_history = max_history_turns
        self._cache = cache or ReplyCache(0)
        self._today = today

    @property
    def model_name(self) -> str:
        return self._llm.model_name

    def ask(self, question: str, history: list[HistoryTurn]) -> QueryResponse:
        timer = _Timer()
        question = " ".join(question.split())
        history = history[-self._max_history:] if self._max_history else []
        catalog = self._catalog.get()
        policy = self._policy(catalog)
        cache_key = (self.model_name, catalog.fingerprint, question.lower(), tuple(history))

        cached = self._cache.get(cache_key)
        if cached is not None:
            response = self._respond_to_reply(question, cached, policy, [], timer, cached=True)
            if response.status in ("answered", "clarification", "unsupported"):
                return response
            # The cached query no longer works; forget it and ask the model
            self._cache.discard(cache_key)
            catalog = self._catalog.get()
            policy = self._policy(catalog)

        base_prompt = build_prompt(question, catalog, history, self._today())
        prompt = base_prompt
        attempts: list[Attempt] = []

        for _ in range(self._max_repairs + 1):
            with timer.generation():
                raw = self._llm.generate(SYSTEM_PROMPT, prompt)
            try:
                reply = parse_reply(raw)
            except ModelOutputError as exc:
                attempts.append(Attempt(stage="model_output", sql=None, error=exc.message))
                prompt = build_format_retry_prompt(base_prompt)
                continue

            if reply.kind != "sql":
                self._cache.put(cache_key, reply)
                return self._respond_to_reply(question, reply, policy, attempts, timer)

            try:
                checked = check_query(reply.sql, policy)
            except QueryRejected as exc:
                attempts.append(Attempt(stage="validation", sql=reply.sql, error=exc.message))
                if not exc.repairable:
                    return self._failure("rejected", question, reply, attempts, timer)
                prompt = build_repair_prompt(base_prompt, reply.sql, exc.message)
                continue

            try:
                result = self._execute(checked, timer)
            except QueryExecutionError as exc:
                attempts.append(Attempt(stage="execution", sql=reply.sql, error=exc.message))
                if exc.schema_changed:
                    # Reload the schema so the repair sees the real tables
                    self._catalog.invalidate()
                    catalog = self._catalog.get()
                    policy = self._policy(catalog)
                    base_prompt = build_prompt(question, catalog, history, self._today())
                if not exc.repairable:
                    return self._failure("failed", question, reply, attempts, timer)
                prompt = build_repair_prompt(base_prompt, reply.sql, exc.message)
                continue

            self._cache.put(cache_key, reply)
            return self._answered(question, reply, checked, result, attempts, timer)

        last = attempts[-1]
        if last.stage == "model_output":
            raise ModelOutputError(last.error)
        status: Status = "rejected" if last.stage == "validation" else "failed"
        return self._failure(status, question, None, attempts, timer)

    def run_sql(self, sql: str) -> QueryResponse:
        """Run SQL written or edited by the user. Same guard, no model call."""
        timer = _Timer()
        reply = ModelReply(kind="sql", sql=sql)
        policy = self._policy(self._catalog.get())
        response = self._respond_to_reply("", reply, policy, [], timer)
        response.model = None
        return response

    def _policy(self, catalog: Catalog) -> GuardPolicy:
        return GuardPolicy(
            database=catalog.database,
            schema=catalog.guard_schema(),
            restricted_columns=self._restricted,
            max_rows=self._max_rows,
        )

    def _execute(self, checked: CheckedQuery, timer: _Timer) -> ResultSet:
        result = self._executor.run(checked)
        timer.execution_ms += result.duration_ms
        return result

    def _respond_to_reply(
        self,
        question: str,
        reply: ModelReply,
        policy: GuardPolicy,
        attempts: list[Attempt],
        timer: _Timer,
        cached: bool = False,
    ) -> QueryResponse:
        """Turn a reply into a response without asking the model for repairs."""
        if reply.kind == "clarification":
            response = self._base("clarification", question, reply, attempts, timer)
            response.message = reply.clarification_question
            response.options = reply.options
        elif reply.kind == "unsupported":
            response = self._base("unsupported", question, reply, attempts, timer)
            response.message = (
                reply.explanation or "This question can't be answered from the database."
            )
        else:
            try:
                checked = check_query(reply.sql, policy)
                result = self._execute(checked, timer)
            except QueryRejected as exc:
                failed = Attempt(stage="validation", sql=reply.sql, error=exc.message)
                attempts = [*attempts, failed]
                return self._failure("rejected", question, reply, attempts, timer)
            except QueryExecutionError as exc:
                if exc.schema_changed:
                    self._catalog.invalidate()
                attempts = [*attempts, Attempt(stage="execution", sql=reply.sql, error=exc.message)]
                return self._failure("failed", question, reply, attempts, timer)
            response = self._answered(question, reply, checked, result, attempts, timer)
        response.cached = cached
        return response

    def _base(
        self,
        status: Status,
        question: str,
        reply: ModelReply | None,
        attempts: list[Attempt],
        timer: _Timer,
    ) -> QueryResponse:
        return QueryResponse(
            status=status,
            question=question,
            explanation=reply.explanation if reply else "",
            assumptions=reply.assumptions if reply else [],
            attempts=attempts,
            model=self.model_name,
            timings=timer.timings(),
        )

    def _answered(
        self,
        question: str,
        reply: ModelReply,
        checked: CheckedQuery,
        result: ResultSet,
        attempts: list[Attempt],
        timer: _Timer,
    ) -> QueryResponse:
        response = self._base("answered", question, reply, attempts, timer)
        response.sql = reply.sql.strip()
        response.executed_sql = checked.sql
        response.result = ResultSetOut(
            columns=[ResultColumn(name=c.name, type=c.type) for c in result.columns],
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            row_limit=result.row_limit,
        )
        logger.info(
            "Answered: %d rows%s, %d failed attempts, tables=%s",
            result.row_count,
            " (truncated)" if result.truncated else "",
            len(attempts),
            ",".join(checked.tables),
        )
        return response

    def _failure(
        self,
        status: Status,
        question: str,
        reply: ModelReply | None,
        attempts: list[Attempt],
        timer: _Timer,
    ) -> QueryResponse:
        last = attempts[-1]
        response = self._base(status, question, reply, attempts[:-1], timer)
        response.message = last.error
        response.sql = last.sql
        logger.info("Query %s: %s", status, last.error)
        return response
