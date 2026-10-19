# Querent

**Ask your database in plain English, and get answers you can check.**

Querent turns a question like *"Which employees earn more than the average
salary of their own department?"* into a MySQL query, checks that the query is
safe, runs it on a read-only connection, and shows the results next to the
exact SQL that produced them.

<!-- After deploying, add the live link and a screenshot here:
**[Live demo](https://your-app.vercel.app)**
![Querent answering a question with a chart](docs/images/screenshot.png)
-->

---

## Why it's different

Most text-to-SQL demos send the question to an LLM and run whatever comes
back. Querent treats the model's output as untrusted and its answers as
something to verify:

- **It asks instead of guessing.** For *"show me the top ones"*, it replies
  *"Top what, and ranked by what?"* with clickable options. For *"what's the
  weather?"*, it explains that the data doesn't cover it.
- **The model can't damage the database.** Three independent layers block
  writes: a syntax-tree SQL guard, read-only database sessions, and a
  SELECT-only account. Each layer is proven by its own tests.
- **It shows its work.** You see the SQL the model wrote, the SQL that
  actually ran, the assumptions it made, and any attempt it had to correct.
- **Accuracy is measured, not assumed.** An evaluation harness scores answers
  by comparing *results* against 54 reference questions, and separately
  reports queries that ran but gave the wrong answer.

## Features

- **Plain-English questions → MySQL**, grounded in the live database schema
- **Follow-up questions:** *"which of those..."*, *"and in 2024?"*
- **Clarifying questions** with one-click options when a question is vague
- **Self-correction:** a query rejected by the guard or by MySQL goes back to
  the model once, with the error
- **Results** as a table, a chart (bar or line) or a single big number, with
  CSV export
- **Edit and run** any query yourself, through the same safety checks
- **Schema explorer:** tables, columns, keys, relationships and example values
- **Polish:** connection status, cancel and retry, saved conversations, dark
  mode, works on phones

## How it works

```mermaid
flowchart LR
    Q[Question + recent turns] --> S[Live schema<br/>tables, keys, value hints]
    S --> M[Gemini<br/>structured JSON]
    M -->|clarification or unsupported| R[Answer]
    M -->|SQL| G[SQL guard<br/>sqlglot syntax tree]
    G -->|rejected but fixable| M
    G --> E[Run read-only<br/>5 s limit, 500 rows]
    E -->|MySQL error, fixable| M
    E --> R
```

1. The backend reads the schema from MySQL at runtime: tables, keys,
   relationships, the values of small text columns, and date ranges. The
   model never has to guess a table name or a spelling.
2. Gemini replies with JSON constrained to a schema. It either writes one
   `SELECT`, asks a clarifying question, or explains why the question can't be
   answered.
3. The **SQL guard** parses the query into a syntax tree and rejects anything
   other than a single read-only `SELECT`. That includes writes, system
   tables, functions like `SLEEP()`, optimizer hints, and MySQL's executable
   comments. The database runs SQL **re-generated from the checked tree**,
   never the model's raw text.
4. The query runs in a read-only session with a time limit and a row cap. A
   fixable failure goes back to the model once.

More detail: [architecture](docs/ARCHITECTURE.md) ·
[design decisions](docs/DECISIONS.md) · [evaluation](docs/EVALUATION.md) ·
[deployment](docs/DEPLOYMENT.md)

## Engineering highlights

| | |
|---|---|
| **Security** | Found by testing that MySQL *executes* code inside `/*!50000 ... */` comments while parsers ignore it. That's why Querent runs re-generated SQL instead of checking the original text and running it. |
| **Defense in depth** | A test sends an `UPDATE` through the *admin* account and it still fails, because every session is read-only. |
| **Correctness** | All 38 reference queries return identical results before and after the guard rewrites them. |
| **Testing** | 225 backend tests (including 53 against a real MySQL server) and 29 frontend tests. None calls the paid AI API: the Gemini client is tested against a mock HTTP transport. |
| **Performance** | The main JavaScript bundle went from 1,042 KB to 393 KB; charts load only when opened. |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Bootstrap 5.3, Chart.js |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy 2, PyMySQL |
| AI | Google Gemini (`google-genai`), structured JSON output |
| SQL safety | sqlglot (MySQL dialect) |
| Database | MySQL 8 |
| Quality | pytest, Vitest, ruff, ESLint, GitHub Actions |

## Run it locally

You need Python 3.10+, Node.js 20+, MySQL 8 and a free
[Gemini API key](https://aistudio.google.com/apikey).

**Backend**

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env               # add your Gemini key and MySQL logins
python -m scripts.setup_db         # database, tables, sample data, read-only user
uvicorn app.main:app --reload      # http://127.0.0.1:8000  (API docs at /docs)
```

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env               # VITE_API_URL=http://127.0.0.1:8000
npm run dev                        # http://localhost:5173
```

The sample database (employees, departments, customers, products, orders) is
generated with a fixed seed, so every setup gives the same answers.

<details>
<summary><b>Configuration</b></summary>

All backend settings are environment variables or entries in `backend/.env`.
Real environment variables take priority.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Any Gemini model with structured output, e.g. `gemini-2.5-flash` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required | The read-only account the app uses |
| `MAX_RESULT_ROWS` | `500` | Row cap per query |
| `QUERY_TIMEOUT_SECONDS` | `5` | MySQL statement time limit |
| `RESTRICTED_COLUMNS` | empty | `table.column` pairs the app may never read |
| `MAX_REPAIR_ATTEMPTS` | `1` | How often a failed query goes back to the model |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per client, for `/query` and `/sql` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend URLs allowed to call the API |

Full list: [backend/.env.example](backend/.env.example)
</details>

<details>
<summary><b>Tests and evaluation</b></summary>

```bash
cd backend
pytest                             # unit tests: no database or API key needed
QG_TEST_MYSQL_ADMIN_URL="mysql+pymysql://root:PASSWORD@127.0.0.1:3306" pytest
                                   # + integration tests on a throwaway querygenie_test database
python -m evals.run --gold         # check the evaluation harness (free)
python -m evals.run                # score the model on 54 questions (uses API quota)

cd ../frontend
npm test && npm run lint && npm run build
```

How answers are scored: [docs/EVALUATION.md](docs/EVALUATION.md)
</details>

<details>
<summary><b>API</b></summary>

| Method | Path | Description |
|---|---|---|
| `POST` | `/query` | `{question, history?}`: answer a question |
| `POST` | `/sql` | `{sql}`: run your own SQL through the same guard (no AI call) |
| `GET` | `/schema` | Tables, columns, keys, relationships and value hints |
| `GET` | `/health` | Database status and the configured model |

Every answer is HTTP 200 with a `status`: `answered`, `clarification`,
`unsupported`, `rejected` or `failed`. Other codes (422, 413, 429, 502, 503)
mean the request itself couldn't be handled.
</details>

## Project structure

```text
backend/
  app/services/   pipeline, sql_guard, catalog, executor, llm, prompts, rate_limit
  app/api/        /query, /sql, /schema, /health
  evals/          54 reference questions, scoring, runner
  tests/          unit/ and integration/
frontend/src/
  components/     conversation turns, results, charts, SQL panel, schema explorer
  lib/            conversation storage, result presentation
docs/             architecture, decisions, evaluation
```

## Limitations and next steps

- **Model accuracy is not yet published:** the evaluation harness is ready;
  a full run against Gemini is the next step.
- **MySQL 8 only:** the guard and the safety settings are MySQL-specific.
- **No user accounts:** fine for the bundled sample data. Real data would
  need authentication in front of the API.
- **Rate limit and cache are in memory:** they work for one server process;
  scaling out would need Redis.

## License

No license has been chosen yet.
