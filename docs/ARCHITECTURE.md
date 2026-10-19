# Architecture

Querent turns a plain-English question into one read-only MySQL query,
runs it safely, and shows the results together with the SQL that produced
them. This document describes how a request flows through the system and
which component is responsible for what. The reasoning behind the main
choices is in [DECISIONS.md](DECISIONS.md).

## Components

```
frontend/ (React + Vite + Bootstrap)
  App.jsx                  conversations, one request at a time, theme, health polling
  services/api.js          fetch wrapper; every failure becomes an ApiError with a code
  lib/conversations.js     localStorage format, migration from v1, follow-up history
  lib/results.js           scalar / chart / table decision, number formatting
  components/              Turn (one question + answer), ResultView, ResultChart,
                           SqlPanel, SchemaExplorer, ConversationList, Composer, Welcome

backend/app/ (FastAPI)
  main.py                  app factory: wiring, error handlers, CORS, body-size limit
  api/query.py             POST /query (question -> answer), POST /sql (user's own SQL)
  api/schema.py            GET /schema, GET /health
  services/pipeline.py     orchestration: prompt -> model -> guard -> execute -> repair
  services/llm.py          model client interface, Gemini client, reply validation
  services/prompts.py      system prompt, schema rendering, conversation context
  services/catalog.py      live schema discovery and profiling, with a TTL cache
  services/sql_guard.py    parse and check generated SQL, produce the SQL to run
  services/executor.py     run checked SQL, convert values, classify database errors
  services/rate_limit.py   per-client sliding-window limit
  database/connection.py   engine with read-only sessions and a statement time limit
  core/config.py           all settings (environment variables / backend/.env)
  models/                  table definitions for the sample database (setup only)
```

## Request flow: `POST /query`

```
question + recent turns
        │
        ▼
 1. Catalog  ─ live schema from MySQL (cached 5 min): tables, columns, keys,
        │      foreign keys, value lists of small text columns, date/number ranges
        ▼
 2. Prompt   ─ system rules + schema + today's date + last 4 turns + question
        │
        ▼
 3. Model    ─ Gemini, JSON constrained to a schema:
        │      {kind: sql | clarification | unsupported, sql, explanation,
        │       assumptions, clarification_question, options}
        │
        ├── clarification / unsupported ──► returned as-is (nothing runs)
        ▼
 4. Guard    ─ sqlglot AST checks; re-generates the SQL with a row cap
        │
        ▼
 5. Execute  ─ read-only session, 5 s statement limit, fetch max_rows + 1
        │
        ├── failure the model might fix ──► repair prompt (with the error) ──► step 3
        ▼                                  (at most MAX_REPAIR_ATTEMPTS times)
 6. Response ─ status, SQL as generated, SQL as executed, results, failed attempts, timings
```

### Response statuses

Every request that reaches the pipeline returns HTTP 200 with a `status`.
HTTP error codes are reserved for problems the user cannot fix by rephrasing.

| `status` | Meaning | What the UI shows |
|---|---|---|
| `answered` | The query ran | results, explanation, assumptions, SQL, timings |
| `clarification` | Too ambiguous to answer | the question and 2-4 clickable options |
| `unsupported` | The data can't answer it, or it asks to change data | the reason and a link to the schema |
| `rejected` | The guard blocked the SQL (nothing ran) | the reason and the rejected SQL |
| `failed` | The database refused or stopped the query | the error, the SQL and a retry button |

| HTTP | `error.code` | Cause |
|---|---|---|
| 422 | `invalid_request` | empty or too-long question, malformed body |
| 413 | `request_too_large` | body over 64 KB |
| 429 | `rate_limited` | over `RATE_LIMIT_PER_MINUTE` (sends `Retry-After`) |
| 502 | `model_unavailable` / `model_output_invalid` | Gemini down, quota hit, or unusable replies |
| 503 | `database_unavailable` | MySQL unreachable or refusing the login |
| 500 | `internal_error` | a bug; details only in the server log |

All error bodies have the shape `{"error": {"code": ..., "message": ...}}`
and carry CORS headers. The catch-all error handler is a middleware inside
CORS; Starlette's default 500 handler is not, so a crash would otherwise
reach the browser as an opaque "Failed to fetch".

### The repair loop

| Failure | Repairable? | Why |
|---|---|---|
| Reply is not valid JSON | yes (asks again) | usually transient |
| Guard: unknown table or column, parse error, forbidden function | yes | the model can pick another approach or say "unsupported" |
| Guard: INSERT/UPDATE/DELETE/DDL | **no** | a write request is never "fixed" into something else |
| MySQL error 1054 / 1064 / 1055 ... | yes | wrong column, syntax, GROUP BY mistakes |
| Timeout (3024), permission denied | **no** | retrying would only repeat the cost |

A repaired query goes through exactly the same guard as the first one. If
MySQL reports a missing table or column that the cached catalog lists, the
schema has changed, so the catalog is reloaded before the repair prompt is
built.

## Safety: three independent layers

1. **SQL guard** (`services/sql_guard.py`). It parses with sqlglot (MySQL
   dialect) and walks the syntax tree:
   - exactly one statement, which is a SELECT, UNION or WITH ... SELECT
   - no INTO, locking clauses, variables, placeholders, optimizer hints or
     executable comments (`/*! ... */`)
   - no functions that stall the server or reveal details about it (SLEEP,
     BENCHMARK, GET_LOCK, LOAD_FILE, USER(), VERSION(), ...)
   - every table is in the catalog (so no `information_schema` or `mysql.*`)
   - every column resolves, and no restricted column is read, `SELECT *`
     included

   The SQL that runs is **re-generated from the checked tree** with comments
   removed and a LIMIT applied. The original text never reaches MySQL, so a
   construct that sqlglot and MySQL would read differently can't slip
   through. (MySQL executes the contents of `/*!50000 ... */`; most parsers
   treat it as a comment.)
2. **Database session** (`database/connection.py`). Every pooled connection
   runs `SET SESSION TRANSACTION READ ONLY` and
   `SET SESSION max_execution_time`. Writes fail with error 1792 even if the
   account could write; tests prove this with the admin account.
3. **Database account** (`scripts/setup_db.py`). The app's user has SELECT
   on one database and nothing else.

Results are capped at `MAX_RESULT_ROWS` (default 500). The guard adds
`LIMIT max_rows + 1`, so the executor can report `truncated: true` honestly.

## Schema catalog

The catalog is read from MySQL at runtime through SQLAlchemy's inspector, so
the assistant works with any database the read-only account can see; the
prompt contains no hand-written schema. For small tables it also records:

- the distinct values of text columns with at most 20 values (e.g. `city`,
  `category`), so filters use exact spellings
- min/max of date and number columns, so the model knows the data runs up to
  2026-09-30 and doesn't guess

Columns whose names look sensitive (`email`, `phone`, `password`, ...) and
restricted columns are never profiled, so their values are never sent to
the model. Restricted columns are also left out of the prompt entirely. The
catalog's fingerprint (a hash of tables, columns and types) is part of the
reply-cache key, so a schema change invalidates cached SQL.

## Conversation context

The server is stateless. The browser keeps conversations in localStorage and
sends the last finished turns with each question as
`{question, sql, reply}`. The prompt marks them as context for resolving
references ("those", "and in 2024?") and says to ignore them when the new
question stands alone. "New conversation" in the UI starts with no context.
The client is untrusted, but a forged history can only influence which
SELECT the model writes, and that SELECT still goes through the guard.

## Data contract

`QueryResponse` (see `backend/app/schemas/query.py`):

```json
{
  "status": "answered",
  "question": "How many customers live in Pune?",
  "message": null,
  "explanation": "Counts customers whose city is Pune.",
  "assumptions": [],
  "options": [],
  "sql": "SELECT COUNT(*) AS customers_in_pune FROM customers WHERE city = 'Pune'",
  "executed_sql": "SELECT\n  COUNT(*) AS customers_in_pune\nFROM customers\nWHERE\n  city = 'Pune'\nLIMIT 501",
  "result": {
    "columns": [{"name": "customers_in_pune", "type": "number"}],
    "rows": [[23]],
    "row_count": 1, "truncated": false, "row_limit": 500
  },
  "attempts": [],
  "model": "gemini-3.8-flash",
  "cached": false,
  "timings": {"generation_ms": 1840.2, "execution_ms": 2.1, "total_ms": 1851.0}
}
```

Rows are arrays rather than objects, so duplicate column names (two
`first_name` columns from a self-join) survive. The `explanation` is written
by the model *before* the query runs and describes the query, never the
results; the UI labels it "What this query does".

## Frontend

- One request in flight at a time. Cancel aborts the fetch (AbortController),
  removes the pending turn and puts the question back in the input box.
- A 1x1 result is shown as a single number. Category + number results with
  2-50 rows can be charted, one measure at a time: plotting columns of
  different scales on one axis would mislead. Time-like labels use a line.
- Chart.js is loaded on demand; the main bundle is 393 KB (121 KB gzipped).
- "Edit" on any SQL runs the edited query through `POST /sql`; "Preview" in
  the schema explorer and "Refresh" on a result do the same. None of these
  call the model.
- Dark mode uses Bootstrap 5.3's `data-bs-theme`, applied before the first
  render to avoid a flash.
- Stored conversations keep at most 100 rows per result and 30
  conversations; older ones are dropped if the browser's storage quota is hit.
