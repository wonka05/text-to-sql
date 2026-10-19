# Querent: ask your database in plain English

Querent turns a question like *"Which employees earn more than the average
salary of their own department?"* into a MySQL query, checks that the query is
safe, runs it on a read-only connection, and shows the results next to the
exact SQL that produced them.

It is built to be trustworthy rather than just impressive:

- **It asks instead of guessing.** Vague questions get a clarifying question
  with clickable options; questions the data can't answer get an explanation
  of what's missing.
- **Generated SQL is treated as untrusted input.** A parser-based guard,
  read-only database sessions and a SELECT-only account each block writes on
  their own.
- **It shows its work.** You see the SQL the model wrote, the SQL that
  actually ran, any assumptions it made, and any attempt it had to correct.
- **Accuracy is measured, not assumed.** An evaluation harness compares
  results against 54 reference questions, separating "the query ran" from
  "the answer was right".

## Features

| | |
|---|---|
| Natural-language questions | Gemini writes one MySQL `SELECT`, grounded in the live schema |
| Follow-up questions | "Which of those...", "and in 2024?" use the conversation's earlier turns |
| Clarification | Ambiguous questions return a question and 2-4 rephrased options |
| Self-correction | If the guard or MySQL rejects a query, the error goes back to the model once |
| Schema explorer | Tables, columns, keys, relationships and value hints, read from the database |
| Results | Table, chart (bar or line, one measure at a time) or a single big number; CSV export |
| Edit and run SQL | Change any query and run it yourself, through the same safety checks |
| Status and errors | Database connection status, cancel, retry, and a clear message for every failure |
| Conversations | Saved in the browser; light and dark themes; works on phones |

## How it stays safe

1. **SQL guard** (`backend/app/services/sql_guard.py`): parses the SQL with
   [sqlglot](https://github.com/tobymao/sqlglot) and checks the syntax tree. It
   allows exactly one SELECT. It rejects writes, `INTO OUTFILE`, locking
   clauses, variables, optimizer hints, MySQL executable comments, functions
   like `SLEEP()` and `LOAD_FILE()`, system schemas, unknown tables or columns,
   and restricted columns. The database runs SQL **re-generated from the
   checked tree**, never the raw model output, with a row limit added.
2. **Read-only session:** every connection runs
   `SET SESSION TRANSACTION READ ONLY` and a 5-second `max_execution_time`.
3. **Read-only account:** the app's MySQL user can only `SELECT` from one
   database.

Results are capped at 500 rows, and the UI says when rows were cut off.
Requests are rate-limited per client. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## How it works

```
React UI ──► POST /query ──► live schema (cached) ──► prompt ──► Gemini (JSON: sql | clarification | unsupported)
                                                                       │
          ◄── results, SQL, explanation, assumptions ◄── execute (read-only) ◄── SQL guard
                                                     └─ on a fixable error: one repair attempt
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Bootstrap 5.3, Chart.js, Vitest |
| Backend | Python 3.10+, FastAPI, Pydantic, SQLAlchemy 2, PyMySQL |
| AI | Google Gemini via `google-genai` (default model `gemini-3.8-flash`), structured JSON output |
| SQL safety | sqlglot (MySQL dialect) |
| Database | MySQL 8 |
| Testing | pytest, Vitest, a results-based evaluation harness, GitHub Actions |

The reasons for each choice, and what was rejected, are in
[docs/DECISIONS.md](docs/DECISIONS.md).

## Getting started

You need Python 3.10+, Node.js 20+, MySQL 8 and a
[Gemini API key](https://aistudio.google.com/apikey).

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / macOS
pip install -r requirements-dev.txt
cp .env.example .env             # then fill in the values
```

In `.env`, set `GEMINI_API_KEY`, your MySQL admin login (`DB_ADMIN_USER` /
`DB_ADMIN_PASSWORD`), and a new password for the app's read-only user
(`DB_PASSWORD`, at least 12 characters). Then:

```bash
python -m scripts.setup_db       # database, tables, sample data, read-only user
python -m scripts.check_db       # confirm the account, its grants and the schema the model sees
uvicorn app.main:app --reload    # http://127.0.0.1:8000, API docs at /docs
```

`python -m scripts.setup_db --reset` rebuilds the sample data. It uses a fixed
seed, so the answers never change.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env             # VITE_API_URL=http://127.0.0.1:8000
npm run dev                      # http://localhost:5173
```

## Configuration

All backend settings are environment variables (or `backend/.env`); real
environment variables take priority. The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Any Gemini model with structured output |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required | The read-only account the app uses |
| `MAX_RESULT_ROWS` | `500` | Row cap per query |
| `QUERY_TIMEOUT_SECONDS` | `5` | MySQL statement time limit |
| `RESTRICTED_COLUMNS` | empty | `table.column` pairs the app may never read |
| `MAX_REPAIR_ATTEMPTS` | `1` | How many times a failed query goes back to the model |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per client IP, for `/query` and `/sql` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | CORS origins, comma-separated |

The full list is in [backend/.env.example](backend/.env.example).

## Testing and evaluation

```bash
cd backend
pytest                           # 172 unit tests; no database or API key needed

# Also run the 53 MySQL integration tests. The fixture creates its own
# querygenie_test database and read-only user, and refuses any other name.
QG_TEST_MYSQL_ADMIN_URL="mysql+pymysql://root:PASSWORD@127.0.0.1:3306" pytest

ruff check app tests evals scripts

python -m evals.run --gold       # check the evaluation harness (no model calls)
python -m evals.run              # measure the model on 54 questions (uses API quota)

cd ../frontend
npm test && npm run lint && npm run build
```

No automated test calls Gemini: unit tests use a scripted fake model, and the
Gemini client is tested against a mock HTTP transport. See
[docs/EVALUATION.md](docs/EVALUATION.md) for how answers are scored.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/query` | `{question, history?}`: answer a question |
| `POST` | `/sql` | `{sql}`: run your own SQL through the same guard (no model call) |
| `GET` | `/schema` | Tables, columns, keys, relationships and value hints |
| `GET` | `/health` | Database reachability and the configured model |

Every `/query` and `/sql` result is HTTP 200 with a `status` of `answered`,
`clarification`, `unsupported`, `rejected` or `failed`. Non-200 responses
(`422`, `413`, `429`, `502`, `503`) mean the request itself couldn't be
handled, and use `{"error": {"code", "message"}}`.

## Project structure

```text
backend/
  app/
    api/            routes: /query, /sql, /schema, /health
    core/           settings, API errors
    database/       engine (read-only sessions), MySQL error codes
    models/         sample database tables (used by setup_db)
    schemas/        request and response models
    services/       pipeline, llm, prompts, catalog, sql_guard, executor, rate_limit
    main.py         app factory
  evals/            questions.json, scoring, runner
  scripts/          setup_db.py, check_db.py
  tests/            unit/ and integration/
frontend/
  src/
    components/     Turn, ResultView, ResultChart, SqlPanel, SchemaExplorer, ...
    lib/            conversation storage, result presentation (with tests)
    services/       API client (with tests)
docs/               ARCHITECTURE.md, DECISIONS.md, EVALUATION.md
```

## Limitations

- **Model accuracy hasn't been measured yet.** The harness is ready and
  self-checked, but a full run against Gemini still has to be done
  (`python -m evals.run`).
- **MySQL 8 only.** The guard, the read-only session settings and the error
  handling are MySQL-specific.
- **No authentication.** That's fine for the bundled sample data. For real
  data, put the API behind authentication: `/schema` reveals the data's shape
  and some column values.
- **The rate limit and reply cache live in one process.** Running several
  server processes would need a shared store such as Redis.
- **The guard re-generates SQL with sqlglot.** All 38 reference queries give
  identical results either way, but rarely used MySQL syntax can be rewritten
  into something MySQL rejects. That fails safely, with an error rather than
  a wrong answer.
- **Conversations are stored only in the browser** (30 conversations, 100
  rows per result).

## License

No license has been chosen yet; the `LICENSE` file is empty. Until one is
added, the default copyright rules apply and others may not reuse the code.
