# QueryGenie: AI Text-to-SQL Assistant

Ask questions about a MySQL database in plain English. QueryGenie uses **Gemini 2.5 Flash** to turn the question into a SQL query, checks that the query is read-only, runs it, and shows the results as a table and a chart.

> "Average salary by department" → `SELECT d.department_name, AVG(e.salary) ... GROUP BY d.department_name` → table + bar chart

## Features

- **Natural language → SQL**: Gemini writes a MySQL `SELECT` query and a short explanation of what it does
- **Read-only guard**: only queries that start with `SELECT` are run; queries containing `DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE` or `CREATE` are rejected
- **Results table** with **CSV export**
- **Automatic bar chart** when the result has two columns (a label and a number)
- **Syntax-highlighted SQL** with a copy button
- **Execution details**: model, response time, rows returned
- **Query history** sidebar, saved in the browser (localStorage)

## Tech Stack

| Layer    | Technologies |
|----------|--------------|
| Frontend | React 19, Vite, Bootstrap 5, Chart.js, PapaParse, react-syntax-highlighter, react-toastify |
| Backend  | Python, FastAPI, Uvicorn, Pydantic |
| Database | MySQL, SQLAlchemy 2.0, PyMySQL |
| AI       | Google Gemini 2.5 Flash (`google-generativeai`) |

## How It Works

1. The React app sends the question to `POST /query`.
2. The backend builds a prompt containing the database schema and rules (SELECT only, JSON output).
3. Gemini returns `{ "sql": "...", "explanation": "..." }`.
4. The SQL validator checks that the query is read-only.
5. The query runs on MySQL through SQLAlchemy, and the rows go back to the frontend along with the SQL, the explanation and execution stats.

## Project Structure

```
AI-SQL-Assistant/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, routers
│   │   ├── api/                  # Routes: /query, /employees
│   │   ├── services/ai_service.py # Prompt + Gemini call
│   │   ├── utils/sql_validator.py # Read-only SQL check
│   │   ├── database/             # Engine, session, connection
│   │   ├── models/               # SQLAlchemy models (6 tables)
│   │   └── schemas/              # Request models
│   ├── scripts/seed_database.py  # Generates sample employees (Faker)
│   ├── datab.sql                 # Database schema
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx               # State and page layout
        ├── components/           # SQL card, results table, history, etc.
        └── services/api.js       # API calls
```

## Database

The schema in `backend/datab.sql` creates the `ai_data_analyst` database with six tables:

- **HR**: `departments`, `employees`
- **Sales**: `customers`, `products`, `orders`, `order_items`

Relationships: `employees → departments`, `orders → customers`, `order_items → orders` and `order_items → products`.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20.19+ or 22.12+
- MySQL
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 1. Set up the database

```bash
mysql -u root -p < backend/datab.sql
```

Add some departments first (the employee seeder assigns `department_id` 1–8), then seed 100 sample employees:

```sql
INSERT INTO departments (department_name) VALUES
('Engineering'), ('Sales'), ('Marketing'), ('Finance'),
('HR'), ('Operations'), ('Support'), ('Product');
```

```bash
cd backend
python scripts/seed_database.py
```

> The seeder only fills `employees`. Add rows to `customers`, `products`, `orders` and `order_items` if you want to query the sales tables.

### 2. Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```
GEMINI_API_KEY=your_api_key_here
```

Set your MySQL username and password in `DATABASE_URL` in `backend/app/database/connection.py`:

```python
DATABASE_URL = "mysql+pymysql://<user>:<password>@localhost/ai_data_analyst"
```

Start the server:

```bash
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

### 3. Run the frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```
VITE_API_URL=http://127.0.0.1:8000
```

```bash
npm run dev
```

Open `http://localhost:5173`. The backend's CORS settings only allow this origin.

## API

### `POST /query`

Request:

```json
{ "question": "Average salary by department" }
```

Response (example):

```json
{
  "question": "Average salary by department",
  "sql": "SELECT d.department_name, AVG(e.salary) AS average_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name;",
  "explanation": "Calculates the average salary for each department.",
  "data": [{ "department_name": "Engineering", "average_salary": 91250.5 }],
  "execution_time": 1843.27,
  "rows_returned": 8,
  "model": "Gemini 2.5 Flash",
  "status": "Success"
}
```

`execution_time` is in milliseconds and includes the Gemini call. If the generated SQL fails the safety check, the response is `{ "error": "Unsafe SQL generated." }`.

### Other endpoints

- `GET /`: welcome message
- `GET /employees`: all employees (SQLAlchemy ORM)

## Example Questions

- Highest paid employee
- Average salary by department
- Products with low stock
- Top 5 customers by total spend
- Employees hired in the last year

## Notes

- AI-generated SQL can be wrong; check the generated query and explanation.
- The keyword check is a basic safeguard. For anything beyond local use, connect with a **read-only MySQL user** (SELECT privilege only).
- Never commit `.env` files or database passwords.
