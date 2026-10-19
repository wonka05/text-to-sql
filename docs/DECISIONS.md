# Technical decisions

Each entry records what was decided, what else was considered, and why.
Dates are when the decision was made (October 2026).

## 1. Keep FastAPI, React/Vite, Bootstrap and MySQL

**Decision:** keep the existing stack.

The original problems were in the logic (unsafe validation, a hand-written
schema, no error handling), not in the frameworks. FastAPI's typed
request/response models fit a JSON API, React with plain `useState` is
enough for one page, and Bootstrap 5.3 provides accessible components and a
built-in dark mode. Switching frameworks would have cost time without fixing
anything.

**Rejected:** Next.js (no server rendering needed), a state library such as
Redux (state is one conversation list), and an ORM query layer for generated
SQL (the model produces SQL text, and the guard needs that text).

## 2. Keep Gemini, change the SDK and the default model

**Decision:** move from `google-generativeai` to `google-genai`, and change
the default model from `gemini-2.5-flash` to `gemini-3.8-flash`.

- `google-generativeai` is the deprecated SDK; `google-genai` is the
  supported one and has typed configuration, structured output, request
  timeouts and bounded retries.
- Google's deprecation page (checked 2026-10-19) says the 2.5 models are
  served only to API keys that have used them before and recommends
  `gemini-3.8-flash` or `gemini-3.5-flash-lite` for new projects. A fresh
  clone with a new key could therefore not use the old default.
- 3.8 Flash costs more per token than 2.5 Flash on the paid tier
  ($0.75 / $3.75 per million input/output tokens until 2026-12-31, vs
  $0.30 / $2.50). Both have a free tier. Set `GEMINI_MODEL` to switch.

**Considered:** switching providers. Rejected because the project already
has a Gemini key, and the free tier matters for a student project. The
pipeline only needs `generate(system_prompt, user_prompt) -> str`
(`LLMClient` in `services/llm.py`), so another provider is one class.

## 3. Structured output with three outcomes, not "always return SQL"

**Decision:** the model replies with JSON constrained by a schema, where
`kind` is `sql`, `clarification` or `unsupported`.

The old prompt forced an answer for every question, so a vague or
impossible question became a confidently wrong query. With an explicit
outcome, the model can ask "top by what?" or say "there is no weather
data". Structured output (`response_json_schema`) also removes the old
crash: a reply wrapped in markdown fences went straight into `json.loads`
and produced a 500. The reply is still validated with Pydantic, because the
model is an untrusted source.

**Rejected:** a separate "is this ambiguous?" model call before generation.
It would double cost and latency for every question, while the single call
can already choose `clarification`.

## 4. A deterministic SQL guard built on a parser (sqlglot)

**Decision:** replace the keyword blocklist with sqlglot parsing and
syntax-tree checks, and execute SQL re-generated from the checked tree.

Measured on the old validator: it rejected 3 of 4 valid test queries (a
column named `created_at` contains "CREATE"; a CTE doesn't start with
"SELECT") and allowed 6 of 7 dangerous ones (`SLEEP`, `GET_LOCK`,
`information_schema`, `@@datadir`, `INTO OUTFILE`, an unbounded cross join).

Executing the re-generated SQL closes a real gap found during testing:
MySQL *runs* the contents of `/*!50000 ... */` comments, while parsers
discard them. With the original text, the guard would check one query and
MySQL would run another. Re-generating from the tree (with comments
stripped) means the database runs exactly what was checked. An integration
test runs all 38 evaluation queries both ways and confirms identical
results.

Optimizer hints are rejected because `/*+ MAX_EXECUTION_TIME(...) */` would
override the session's time limit.

**Rejected:** a prompt instruction as the only control (the model can be
talked out of it), and a regex validator (it can't tell identifiers, string
literals and keywords apart).

## 5. Defence in depth at the database

**Decision:** keep the SELECT-only account and also make every session READ
ONLY with `max_execution_time`.

The guard is code and could have a bug. The session settings don't depend
on it: a test runs an UPDATE through the engine using the *admin* account
and it still fails (error 1792). `max_execution_time` stops expensive
queries (a three-way self-join of `order_items` is stopped at 1 s in tests).
The SQLAlchemy pool applies both settings on every new connection.

## 6. Discover the schema at runtime

**Decision:** read tables, columns, keys and foreign keys from MySQL, plus a
small data profile, cached for 5 minutes.

The hand-written schema in the old prompt had to be kept in sync manually
and couldn't describe any other database. Value lists for small text
columns stop the model guessing spellings ("electronics" vs "Electronics").
Date ranges tell it the data ends in September 2026, which matters for "this
month" questions. Profiling skips large tables, sensitive-looking columns
and restricted columns.

**Rejected:** embedding-based schema retrieval. With six tables the whole
rendered schema is about 400 tokens (measured), and the full prompt about
1,100-1,300. Retrieval would add a dependency and a failure mode without
measurable benefit at this size. It becomes worth it once the schema no
longer fits comfortably in the prompt, roughly 100+ tables.

## 7. One bounded repair attempt

**Decision:** when the guard or MySQL rejects a query for a reason the model
might fix, send the error back once (`MAX_REPAIR_ATTEMPTS=1`).

Common first-attempt failures (a wrong column name, an `ONLY_FULL_GROUP_BY`
error) are usually fixed when the model sees the exact message. More than
one retry mostly adds cost. Writes, timeouts and permission errors are not
retried. The UI shows failed attempts so a correction is never hidden.

## 8. No second model call to "explain the results"

**Decision:** the explanation is written before execution and describes the
query. The result table (or a single big number) is the answer.

A model summarising rows can misstate numbers, and that is the exact
failure this project tries to prevent. It would also double the cost of
every question. The UI labels the text "What this query does" so it isn't
read as a claim about the data.

## 9. Conversation history is kept in the browser

**Decision:** the browser stores conversations and sends the last 4 turns
with each question; the server stores nothing.

This needs no database tables, no accounts, and no session expiry logic.
The trade-off is that history is per browser. Turns sent by the client are
untrusted, but they can only influence which SELECT is generated, and that
still passes the guard.

## 10. Cost and abuse controls sized for a public demo

- Per-IP rate limit on `/query` and `/sql` (20 per minute, in memory). One
  process is enough for this project; several processes would need Redis.
- An LRU cache of model replies, keyed on model + schema fingerprint +
  normalised question + history. Clicking an example question twice costs
  one model call. The cached SQL is still checked and executed again, so
  results stay fresh.
- Question length (500 chars), history length, body size (64 KB), result
  rows (500) and execution time (5 s) are all capped.

**Not added:** authentication. The app exposes a sample database through a
read-only account, so an account system would add complexity without
protecting anything. For real data, put the API behind authentication;
the `/schema` endpoint and the value hints reveal the data's shape.

## 11. Tests that don't call the model

**Decision:** unit tests use a scripted fake model; integration tests use a
real MySQL server; the evaluation harness is the only thing that calls
Gemini, and only when run on purpose.

- `tests/unit`: guard, pipeline, prompts, API, parsing, scoring, and the
  Gemini client against a mock HTTP transport (checks the real request body
  the SDK sends).
- `tests/integration`: a fixture creates its own `*_test` database and
  read-only user, then tests catalog discovery, the executor, timeouts,
  read-only sessions, truncation, and the API end to end. It refuses to use
  a database whose name doesn't end in `_test`.
- `evals/`: 54 questions with gold SQL or expected outcomes; see
  [EVALUATION.md](EVALUATION.md).

## 12. Frontend presentation choices

- **Results as `columns` + `rows` arrays**, not a list of objects. Objects
  drop duplicate column names and JavaScript reorders numeric keys.
- **One measure per chart, chosen by the user.** Plotting `avg_salary` and
  `employees` on one axis would make one of them unreadable; two y-axes are
  a well-known way to mislead.
- **Single values as one big number**, not a one-bar chart.
- **Chart.js loaded on demand** and the syntax highlighter limited to SQL:
  the main bundle went from 1,042 KB to 393 KB.
- **Bootstrap's `data-bs-theme`** replaced about 60 lines of hand-written
  dark-mode overrides, which missed some components.
