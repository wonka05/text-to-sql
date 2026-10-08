# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

QueryGenie: a natural-language-to-SQL assistant. A user types a question, Gemini 2.5 Flash produces a MySQL `SELECT`, the backend runs it against a local MySQL database, and the React UI shows the SQL, an explanation, execution stats, a results table, and (sometimes) a bar chart.

- `backend/`: FastAPI + SQLAlchemy + PyMySQL + `google-generativeai`
- `frontend/`: React 19 + Vite + Bootstrap/react-bootstrap + Chart.js
- `database/` and `docs/` are empty placeholders. `frontend/README.md` is the stock Vite template.

## Workflow

Never commit to, merge into, or rewrite `main`. Do all work on a new branch and leave merging to the owner (via a GitHub PR).

## Commands

Backend (run from `backend/` with the venv in `backend/venv` active; imports are rooted at `app.`, so the working directory matters):

```bash
pip install -r requirements-dev.txt          # runtime deps (requirements.txt) + Faker for seeding
python -m scripts.setup_db                   # create DB, tables, sample data and the read-only app user
python -m scripts.setup_db --reset           # drop all tables and rebuild with fresh sample data
python -m scripts.check_db                   # show which account the app connects as, its grants, row counts
uvicorn app.main:app --reload                # API on http://127.0.0.1:8000 (docs at /docs)
```

Frontend (run from `frontend/`):

```bash
npm install
npm run dev       # Vite on http://localhost:5173
npm run build
npm run lint      # ESLint (flat config in eslint.config.js)
```

There is no automated test suite yet: no pytest and no JS tests.

## Configuration

- All backend settings live in `app/core/config.py` (`pydantic-settings`), read from environment variables or the gitignored `backend/.env` (template: `.env.example`). Missing required values fail at startup. Import `settings` from there; never call `os.getenv` or put credentials in code.
- **Real environment variables override `.env`.** This machine has a Windows user-level `DB_PASSWORD` variable that silently replaces the `.env` value; if the app can't log in, check `[Environment]::GetEnvironmentVariable('DB_PASSWORD','User')`.
- Two DB accounts: the app connects as `DB_USER` (`querygenie_ro`, SELECT-only on `DB_NAME`, created by `setup_db`). `DB_ADMIN_USER`/`DB_ADMIN_PASSWORD` are used only by `scripts/setup_db.py` and must never be set on a server.
- `ALLOWED_ORIGINS` (comma-separated) controls CORS; default `http://localhost:5173`.
- `frontend/.env` needs `VITE_API_URL` (e.g. `http://127.0.0.1:8000`). There is no Vite proxy; the frontend calls the backend directly. Anything in a `VITE_*` variable is public in the browser bundle.

## Architecture

### Request flow (`POST /query`)

`frontend/src/services/api.js` → `backend/app/api/query.py`:

1. `services/ai_service.generate_sql(question)` puts the question into a prompt and calls Gemini. It runs `json.loads` on the raw response text and expects `{"sql": ..., "explanation": ...}`. Gemini output that is not valid JSON (e.g. fenced in markdown) is not caught and surfaces as a 500.
2. `utils/sql_validator.validate_sql` requires the SQL to start with `SELECT`. It then rejects any SQL whose uppercased text contains a forbidden keyword (`DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`). This is a raw substring match, so identifiers such as `created_at` or `updated_by` would also be rejected.
3. The SQL runs via `engine.connect()` + `text(sql)`. Rows come back as `result.mappings().all()`.
4. The response contains `question, sql, explanation, data, execution_time, rows_returned, model, status`. `execution_time` covers the whole request, Gemini call included. `model` is `settings.gemini_model`.

Unsafe SQL returns **HTTP 200** with `{"error": "..."}` rather than an error status. `api.js` treats either `!response.ok` or `data.error` as a failure.

### The schema is defined in two places

When you add or change a table or column, keep both in sync:

- `backend/app/models/*.py`: the source of truth. `scripts/setup_db.py` creates the tables from these models (`Base.metadata.create_all`); there is no `.sql` DDL file. `/query` executes raw SQL and does not use the models at runtime.
- The prompt string in `backend/app/services/ai_service.py`: the schema the LLM sees. Gemini can only query tables and columns listed here.

Tables: `departments`, `employees`, `customers`, `products`, `orders`, `order_items`.

Sample data comes from `build_rows()` in `scripts/setup_db.py`, generated with a fixed seed so every reset produces identical rows (dates are fixed, ending 2026-09-30). Keep it deterministic: benchmark answers depend on it.

### Frontend

- All state lives in `App.jsx`, with no router or state library. The message list is persisted to `localStorage["querygenie-history"]` and the theme to `localStorage["theme"]`.
- `App.jsx` maps the snake_case API fields to camelCase when it stores a message (`execution_time` → `executionTime`, `rows_returned` → `rowsReturned`). Already-saved history uses the camelCase shape, so changing these field names breaks old entries.
- `components/ResultsTable.jsx` handles CSV export (PapaParse) and charting. It renders a Chart.js `Bar` chart only when the result has exactly 2 columns, the first value is a string, and the second is numeric.
- Dark mode works by toggling the `dark-mode` class on `<body>`. The overrides are `body.dark-mode ...` rules in `src/index.css`.
