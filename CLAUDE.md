# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

QueryGenie: a natural-language-to-SQL assistant. A user types a question, Gemini 2.5 Flash produces a MySQL `SELECT`, the backend runs it against a local MySQL database, and the React UI shows the SQL, an explanation, execution stats, a results table, and (sometimes) a bar chart.

- `backend/`: FastAPI + SQLAlchemy + PyMySQL + `google-generativeai`
- `frontend/`: React 19 + Vite + Bootstrap/react-bootstrap + Chart.js
- `database/` and `docs/` are empty placeholders. The root `README.md` is empty, and `frontend/README.md` is the stock Vite template.

## Commands

Backend (run from `backend/`; imports are rooted at `app.`, so the working directory matters):

```bash
pip install -r requirements.txt              # requirements.txt is a UTF-16 `pip freeze` dump
mysql -u root -p < datab.sql                 # creates the ai_data_analyst DB + tables (no data)
uvicorn app.main:app --reload                # API on http://127.0.0.1:8000
python -m app.database.test_connection       # DB connectivity check
python scripts/seed_database.py              # inserts 100 fake employees (needs department_id 1–8 to exist)
python test_api.py                           # calls Gemini once and prints the generated SQL; needs GEMINI_API_KEY
```

Frontend (run from `frontend/`):

```bash
npm install
npm run dev       # Vite on http://localhost:5173
npm run build
npm run lint      # ESLint (flat config in eslint.config.js)
```

There is no automated test suite: no pytest and no JS tests. `test_api.py` and `test_connection.py` are manual scripts.

## Configuration

- `backend/.env` (gitignored; copy from `.env.example`) holds `GEMINI_API_KEY` and the `DB_*` settings, loaded through `python-dotenv`. `database/connection.py` builds the URL with `URL.create` (so special characters in the password are escaped) and raises at import if `DB_NAME`, `DB_USER` or `DB_PASSWORD` is missing. Never put credentials back into code.
- `frontend/.env` needs `VITE_API_URL` (e.g. `http://127.0.0.1:8000`). There is no Vite proxy; the frontend calls the backend directly.
- CORS in `backend/app/main.py` allows only `http://localhost:5173`. Serving the frontend from any other origin or port requires updating it.

## Architecture

### Request flow (`POST /query`)

`frontend/src/services/api.js` → `backend/app/api/query.py`:

1. `services/ai_service.generate_sql(question)` puts the question into a prompt and calls Gemini. It runs `json.loads` on the raw response text and expects `{"sql": ..., "explanation": ...}`. Gemini output that is not valid JSON (e.g. fenced in markdown) is not caught and surfaces as a 500.
2. `utils/sql_validator.validate_sql` requires the SQL to start with `SELECT`. It then rejects any SQL whose uppercased text contains a forbidden keyword (`DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`). This is a raw substring match, so identifiers such as `created_at` or `updated_by` would also be rejected.
3. The SQL runs via `engine.connect()` + `text(sql)`. Rows come back as `result.mappings().all()`.
4. The response contains `question, sql, explanation, data, execution_time, rows_returned, model, status`. `execution_time` covers the whole request, Gemini call included. `model` is a hardcoded string, so it needs updating if the Gemini model changes.

Unsafe SQL returns **HTTP 200** with `{"error": "..."}` rather than an error status. `api.js` treats either `!response.ok` or `data.error` as a failure.

### The schema is defined in three places

When you add or change a table or column, keep all three in sync:

- `backend/datab.sql`: the actual DDL
- `backend/app/models/*.py`: SQLAlchemy ORM models. Only `Employee` is used, by `GET /employees`; `/query` executes raw SQL and does not use the models.
- The prompt string in `backend/app/services/ai_service.py`: the schema the LLM sees. Gemini can only query tables and columns listed here.

Tables: `departments`, `employees`, `customers`, `products`, `orders`, `order_items`.

`SessionLocal` is defined in both `database/connection.py` and `database/session.py`. The `get_db` dependency uses the one in `session.py`.

### Frontend

- All state lives in `App.jsx`, with no router or state library. The message list is persisted to `localStorage["querygenie-history"]` and the theme to `localStorage["theme"]`.
- `App.jsx` maps the snake_case API fields to camelCase when it stores a message (`execution_time` → `executionTime`, `rows_returned` → `rowsReturned`). Already-saved history uses the camelCase shape, so changing these field names breaks old entries.
- `components/ResultsTable.jsx` handles CSV export (PapaParse) and charting. It renders a Chart.js `Bar` chart only when the result has exactly 2 columns, the first value is a string, and the second is numeric.
- Dark mode works by toggling the `dark-mode` class on `<body>`. The overrides are `body.dark-mode ...` rules in `src/index.css`.
