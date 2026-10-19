# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Querent (formerly QueryGenie): a natural-language-to-SQL assistant. Internal identifiers keep the old name on purpose: the DB account `querygenie_ro`, the test databases, and the localStorage keys (renaming them would break existing logins and saved conversations). Gemini writes one MySQL `SELECT` (or asks for clarification, or says the question is unsupported), a sqlglot-based guard checks it, the backend runs it on a read-only connection, and the React UI shows results, the SQL, assumptions and any self-corrections.

- `backend/`: FastAPI + SQLAlchemy + PyMySQL + `google-genai` + sqlglot
- `frontend/`: React 19 + Vite + Bootstrap 5.3 + Chart.js
- `docs/`: ARCHITECTURE.md (request flow, safety layers, data contract), DECISIONS.md (why), EVALUATION.md (harness and results)
- `database/` is an empty placeholder.

## Workflow

Never commit to, merge into, or rewrite `main`. Do all work on a new branch and leave merging to the owner (via a GitHub PR).

## Commands

Backend (run from `backend/` with the venv in `backend/venv` active; imports are rooted at `app.`, so the working directory matters):

```bash
pip install -r requirements-dev.txt          # runtime deps + Faker, pytest, httpx2, ruff
python -m scripts.setup_db                   # create DB, tables, sample data and the read-only app user
python -m scripts.setup_db --reset           # drop all tables and rebuild with fresh sample data
python -m scripts.check_db                   # account, grants, session settings, row counts, schema the model sees
uvicorn app.main:app --reload                # API on http://127.0.0.1:8000 (docs at /docs)
pytest                                       # unit tests (no DB, no API key)
QG_TEST_MYSQL_ADMIN_URL=mysql+pymysql://root:PW@127.0.0.1:3306 pytest   # + MySQL integration tests
pytest tests/unit/test_sql_guard.py -k restricted                        # single test file / test
ruff check app tests evals scripts
python -m evals.run --gold                   # eval harness self-check, no model calls
python -m evals.run                          # real eval: ~60 Gemini calls; needs the user's OK (costs quota)
```

Frontend (run from `frontend/`):

```bash
npm install
npm run dev       # Vite on http://localhost:5173
npm test          # Vitest (src/lib, src/services)
npm run lint      # ESLint (flat config in eslint.config.js)
npm run build
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest with a MySQL 8 service, `evals.run --gold`, and frontend lint/test/build.

## Configuration

- All backend settings live in `app/core/config.py` (`pydantic-settings`), read from environment variables or the gitignored `backend/.env` (template: `.env.example`). Use `get_settings()`; never call `os.getenv` or put credentials in code. Tests build `Settings(_env_file=None, ...)` directly.
- **Real environment variables override `.env`.** This machine has a Windows user-level `DB_PASSWORD` variable that silently replaces the `.env` value; if the app can't log in, check `[Environment]::GetEnvironmentVariable('DB_PASSWORD','User')`.
- Two DB accounts: the app connects as `DB_USER` (`querygenie_ro`, SELECT-only on `DB_NAME`, created by `setup_db`). `DB_ADMIN_USER`/`DB_ADMIN_PASSWORD` are used only by `scripts/setup_db.py` and must never be set on a server.
- The integration-test fixture creates its own `querygenie_test` database and `querygenie_pytest_ro` user on whatever server `QG_TEST_MYSQL_ADMIN_URL` points at, and refuses database names not ending in `_test`.
- `ALLOWED_ORIGINS` (comma-separated) controls CORS; default `http://localhost:5173`.
- `frontend/.env` needs `VITE_API_URL` (e.g. `http://127.0.0.1:8000`). There is no Vite proxy. Anything in a `VITE_*` variable is public in the browser bundle.

## Architecture

### Request flow (`POST /query`), in `app/services/pipeline.py`

1. `CatalogProvider.get()` returns the live schema (`services/catalog.py`): tables, columns, PK/FK, value lists of small text columns, date/number ranges. Cached for `SCHEMA_CACHE_SECONDS`; reloaded early when MySQL reports a missing table/column (1054/1146).
2. `prompts.build_prompt` combines the schema, today's date, the last 4 turns the client sent, and the question. `SYSTEM_PROMPT` holds the rules.
3. `GeminiClient.generate` (`services/llm.py`) asks for JSON matching `REPLY_SCHEMA`: `kind` is `sql`, `clarification` or `unsupported`. `parse_reply` validates it with Pydantic.
4. `sql_guard.check_query` parses with sqlglot and walks the AST (single SELECT/UNION/CTE; no writes, INTO, locks, hints, variables, placeholders, `/*!` comments, forbidden functions, other schemas, unknown tables/columns, restricted columns). It returns **re-generated, pretty-printed SQL with `LIMIT max_rows+1`**; that, not the model's text, is what runs.
5. `QueryExecutor.run` (`services/executor.py`) runs it with `exec_driver_sql(..., no_parameters=True)` so `%` and `:name` aren't treated as bind params, fetches `max_rows+1`, converts values to JSON types, and classifies MySQL errors (timeout 3024 and permission errors are not repairable).
6. On a repairable guard or DB error, the pipeline sends a repair prompt with the error, up to `MAX_REPAIR_ATTEMPTS`. Repaired SQL goes through the same guard.

Pipeline outcomes are HTTP 200 with `status` in `answered | clarification | unsupported | rejected | failed`. Infrastructure problems raise `AppError` subclasses (`core/errors.py`), which become `{"error": {"code", "message"}}` with 422/413/429/502/503. A middleware registered before CORS turns unexpected exceptions into JSON 500s that keep CORS headers.

Every DB session is `READ ONLY` with `max_execution_time` (`database/connection.py`, set in a pool `connect` event). `POST /sql` runs user-written SQL through the same guard without calling the model. `ReplyCache` reuses model replies for identical (model, schema fingerprint, question, history) keys; the SQL is still re-checked and re-run.

### The schema the app queries

- `backend/app/models/*.py` define the sample tables; `scripts/setup_db.py` creates them (`Base.metadata.create_all`) and fills them with `build_rows()`, which uses a fixed seed so every reset is identical (dates end 2026-09-30). Keep it deterministic: `evals/questions.json` gold answers depend on it.
- The app itself does **not** use the models at runtime: the prompt and guard use the live catalog, so a new table or column is picked up automatically (after the cache TTL). After changing the sample schema, check `evals/questions.json` and run `python -m evals.run --gold`.

Tables: `departments`, `employees`, `customers`, `products`, `orders`, `order_items`.

### Frontend

- State lives in `App.jsx` (no router or state library). Conversations are stored in `localStorage["querygenie-conversations"]` as `{conversations, activeId}`. Each turn keeps the API's `QueryResponse` unchanged (snake_case). `lib/conversations.js` migrates the old `localStorage["querygenie-history"]` format once and trims stored results to 100 rows.
- `buildHistory` sends the last 4 finished turns as `{question, sql, reply}` with each question. "New" starts a conversation with no context.
- Results are `{columns: [{name, type}], rows: [[...]]}` (arrays, so duplicate column names survive). `lib/results.js` decides scalar tile vs chart vs table; `ResultChart` (lazy-loaded Chart.js) plots one measure at a time.
- Theme is Bootstrap's `data-bs-theme` on `<html>`, set by an inline script in `index.html` before render and by `App.jsx` afterwards. Custom CSS in `src/index.css` uses Bootstrap CSS variables only.
