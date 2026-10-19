"""Decide whether a SQL string is safe to run, and produce the SQL to run.

Generated SQL is untrusted input, so it is parsed into a syntax tree (with
sqlglot, MySQL dialect) and checked node by node rather than by searching the
text for keywords. Keyword search both blocks valid queries (a column called
`created_at` contains "CREATE") and misses dangerous ones (`SELECT SLEEP(1e9)`).

The checks:
  1. Exactly one statement, and it is a SELECT (WITH ... SELECT and UNION too).
  2. No writes, INTO, locking clauses, variables, placeholders, optimizer
     hints (`MAX_EXECUTION_TIME` could lift the time limit) or MySQL
     executable comments (`/*! ... */`, which MySQL runs but parsers skip).
  3. No functions that stall the server or reveal details about it.
  4. Every table is in the catalog (no `information_schema`, `mysql`, ...).
  5. Every column exists, and no restricted column is read (including via *).
  6. A row cap: LIMIT is added, or lowered if larger than the cap.

What runs is the SQL re-generated from the checked syntax tree with comments
removed, never the original text. That way the database runs exactly what
was checked, even if MySQL and sqlglot would read the original differently.

This guard is one of three layers. The database account can only SELECT, and
every session is READ ONLY with a statement time limit
(see app/database/connection.py).
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

MAX_SQL_LENGTH = 10_000

# Not allowed anywhere in the tree
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.DML,  # INSERT, UPDATE, DELETE, MERGE
    exp.DDL,  # CREATE, DROP-like, ALTER
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,  # anything sqlglot could not parse into a known statement
    exp.Into,  # SELECT ... INTO @var / INTO OUTFILE
    exp.Lock,  # FOR UPDATE / FOR SHARE
    exp.Hint,  # /*+ MAX_EXECUTION_TIME(...) */ and other optimizer hints
    exp.SessionParameter,  # @@system_variable
    exp.Parameter,  # @user_variable
    exp.Placeholder,  # ? and :name
)

FORBIDDEN_FUNCTIONS = frozenset({
    # Stall the server or hold locks past the end of the query
    "SLEEP", "BENCHMARK", "GET_LOCK", "RELEASE_LOCK", "RELEASE_ALL_LOCKS",
    "IS_FREE_LOCK", "IS_USED_LOCK", "MASTER_POS_WAIT", "SOURCE_POS_WAIT",
    "WAIT_FOR_EXECUTED_GTID_SET", "WAIT_UNTIL_SQL_THREAD_AFTER_GTIDS",
    # Read server files or reveal details about the server and the session
    "LOAD_FILE", "USER", "CURRENT_USER", "SESSION_USER", "SYSTEM_USER",
    "CURRENT_ROLE", "ROLES_GRAPHML", "VERSION", "CURRENT_VERSION", "DATABASE",
    "SCHEMA", "CURRENT_SCHEMA", "CONNECTION_ID", "LAST_INSERT_ID", "ROW_COUNT",
    "FOUND_ROWS", "PS_CURRENT_THREAD_ID", "PS_THREAD_ID", "STATEMENT_DIGEST",
    "STATEMENT_DIGEST_TEXT",
})

ALLOWED_ROOTS = (exp.Select, exp.SetOperation, exp.Subquery)


class QueryRejected(Exception):
    """The SQL is not allowed to run.

    `repairable` tells the pipeline whether asking the model to fix the query
    makes sense. Unknown columns are worth a retry; a DELETE is not.
    """

    def __init__(self, reason: str, message: str, repairable: bool = True):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.repairable = repairable


@dataclass(frozen=True)
class GuardPolicy:
    database: str
    # {table: {column: type}}, all lower case (Catalog.guard_schema())
    schema: dict[str, dict[str, str]]
    restricted_columns: frozenset[tuple[str, str]] = frozenset()
    max_rows: int = 500


@dataclass(frozen=True)
class CheckedQuery:
    # The SQL to execute: re-generated from the checked tree, with the row cap
    sql: str
    tables: tuple[str, ...]
    # True when the guard added or lowered the LIMIT (to max_rows + 1, so
    # the executor can tell whether rows were cut off)
    limit_applied: bool


def check_query(sql: str, policy: GuardPolicy) -> CheckedQuery:
    sql = (sql or "").strip()
    if not sql:
        raise QueryRejected("empty", "The query is empty.")
    if len(sql) > MAX_SQL_LENGTH:
        raise QueryRejected("too_long", f"The query is longer than {MAX_SQL_LENGTH} characters.")
    if "/*!" in sql:
        raise QueryRejected(
            "executable_comment",
            "MySQL executable comments (/*! ... */) are not allowed.",
        )

    tree = _parse_single_select(sql)
    _check_nodes(tree)
    tables = _check_tables(tree, policy)
    _check_columns(tree, policy)
    limit_applied = _apply_row_cap(tree, policy.max_rows)

    return CheckedQuery(
        # Pretty-printed so people can read what ran; whitespace only, same query
        sql=tree.sql(dialect="mysql", comments=False, pretty=True),
        tables=tables,
        limit_applied=limit_applied,
    )


def _parse_single_select(sql: str) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read="mysql") if s is not None]
    except ParseError as exc:
        first_error = str(exc).splitlines()[0]
        raise QueryRejected("parse_error", f"The SQL could not be parsed: {first_error}") from exc

    if len(statements) != 1:
        raise QueryRejected(
            "multiple_statements",
            "Only a single SQL statement is allowed.",
            repairable=len(statements) > 1,
        )

    tree = statements[0]
    if not isinstance(tree, ALLOWED_ROOTS) or (
        isinstance(tree, exp.Subquery) and not isinstance(tree.unnest(), ALLOWED_ROOTS)
    ):
        raise QueryRejected(
            "not_select",
            "Only read-only SELECT queries are allowed.",
            repairable=False,
        )
    return tree


def _check_nodes(tree: exp.Expression) -> None:
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            writes = (exp.DML, exp.DDL, exp.Drop, exp.Alter, exp.TruncateTable)
            raise QueryRejected(
                "forbidden_syntax",
                f"The query uses something that is not allowed: {_describe(node)}.",
                repairable=not isinstance(node, writes),
            )
        if isinstance(node, exp.Func):
            name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
            if name.upper() in FORBIDDEN_FUNCTIONS:
                raise QueryRejected(
                    "forbidden_function",
                    f"The function {name.upper()}() is not allowed.",
                )


def _describe(node: exp.Expression) -> str:
    labels = {
        exp.Into: "SELECT ... INTO",
        exp.Lock: "a locking clause (FOR UPDATE / FOR SHARE)",
        exp.Hint: "an optimizer hint",
        exp.SessionParameter: "a system variable (@@...)",
        exp.Parameter: "a user variable (@...)",
        exp.Placeholder: "a bind placeholder",
        exp.Command: "an unsupported statement",
    }
    for node_type, label in labels.items():
        if isinstance(node, node_type):
            return label
    return f"a {node.key.upper()} statement"


def _check_tables(tree: exp.Expression, policy: GuardPolicy) -> tuple[str, ...]:
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    used = []
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if not name:
            raise QueryRejected(
                "table_function", "Table functions such as JSON_TABLE are not supported."
            )
        if table.catalog or (table.db and table.db.lower() != policy.database.lower()):
            schema = ".".join(p for p in (table.catalog, table.db) if p)
            raise QueryRejected(
                "other_schema",
                f"Only tables in the '{policy.database}' database can be queried, not '{schema}'.",
            )
        if name == "dual" or (name in cte_names and not table.db):
            continue
        if name not in policy.schema:
            known = ", ".join(sorted(policy.schema))
            raise QueryRejected(
                "unknown_table",
                f"Table '{table.name}' does not exist. Available tables: {known}.",
            )
        used.append(name)
    return tuple(sorted(set(used)))


def _check_columns(tree: exp.Expression, policy: GuardPolicy) -> None:
    # MySQL column names are case-insensitive, so compare in lower case.
    # This works on a copy; the original tree is what gets executed.
    lowered = tree.copy()
    for identifier in lowered.find_all(exp.Identifier):
        identifier.set("this", identifier.this.lower())

    try:
        qualified = qualify(
            lowered,
            schema=policy.schema,
            dialect="mysql",
            validate_qualify_columns=True,
            quote_identifiers=False,
            identify=False,
        )
    except OptimizeError as exc:
        raise QueryRejected("unknown_column", _column_error(str(exc))) from exc
    except SqlglotError as exc:
        raise QueryRejected("unverifiable", f"The query could not be checked: {exc}") from exc

    if not policy.restricted_columns:
        return
    for scope in traverse_scope(qualified):
        for column in scope.columns:
            source = scope.sources.get(column.table)
            # Columns of derived tables and CTEs are checked in their own scope
            if isinstance(source, exp.Table):
                pair = (source.name.lower(), column.name.lower())
                if pair in policy.restricted_columns:
                    raise QueryRejected(
                        "restricted_column",
                        f"Column {pair[0]}.{pair[1]} is restricted and cannot be queried."
                        " List only the columns you need (SELECT * would include it).",
                    )


def _column_error(detail: str) -> str:
    detail = detail.splitlines()[0]
    if "could not be resolved" in detail or "Unknown column" in detail:
        return f"{detail} (the column does not exist, or is ambiguous without a table alias)."
    return f"The query's columns could not be resolved: {detail}"


def _apply_row_cap(tree: exp.Expression, max_rows: int) -> bool:
    """Make sure at most max_rows + 1 rows come back.

    Fetching one extra row lets the executor report that results were cut
    off. A smaller LIMIT the query already has (e.g. "top 5") is kept.
    """
    target = tree.unnest() if isinstance(tree, exp.Subquery) else tree
    cap = max_rows + 1
    current = target.args.get("limit")
    if current is not None:
        value = current.expression
        if isinstance(value, exp.Literal) and value.is_int and int(value.this) <= max_rows:
            return False
    target.set("limit", exp.Limit(expression=exp.Literal.number(cap)))
    return True
