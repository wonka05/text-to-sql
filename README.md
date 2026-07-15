# QueryGenie - AI-Powered Text-to-SQL Assistant

QueryGenie is a full-stack AI application that translates natural language questions into executable MySQL queries using Google's Gemini API. The system validates generated SQL, executes safe read-only queries on a MySQL database, and presents the results through an interactive React interface with charts, execution statistics, and conversation history.

The project demonstrates the integration of Large Language Models (LLMs) with modern web technologies to simplify database querying for users without SQL expertise.

---

## Features

- Natural language to SQL conversion using Gemini
- Secure SQL validation (SELECT queries only)
- MySQL query execution using SQLAlchemy
- AI-generated SQL explanations
- Interactive data visualization with Chart.js
- Query result table with CSV export
- Conversation history with local persistence
- Execution statistics and query metadata
- Syntax-highlighted SQL editor
- Light and Dark theme support
- Responsive React interface

---

## Tech Stack

### Frontend

- React
- Vite
- Bootstrap 5
- React Icons
- React Toastify
- Chart.js
- React Chart.js 2
- React Syntax Highlighter
- PapaParse

### Backend

- FastAPI
- SQLAlchemy
- MySQL
- Google Gemini API
- python-dotenv
- Uvicorn

---

## Architecture

```text
                User
                  │
                  ▼
        React Frontend (Vite)
                  │
                  ▼
          FastAPI REST API
                  │
        SQL Generation (Gemini)
                  │
                  ▼
         SQL Validation Layer
                  │
                  ▼
        SQLAlchemy + MySQL
                  │
                  ▼
          Query Results
                  │
                  ▼
 React Tables • Charts • CSV Export
```

---

## Project Structure

```text
text-to-sql/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── database/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── utils/
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── layout/
│   │   ├── services/
│   │   ├── App.jsx
│   │   └── main.jsx
│   │
│   ├── package.json
│   └── vite.config.js
│
├── database.sql
├── LICENSE
└── README.md
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/wonka05/text-to-sql.git
cd text-to-sql
```

---

## Backend Setup

Create a virtual environment.

```bash
python -m venv .venv
```

Activate it.

Windows

```bash
.venv\Scripts\activate
```

Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Create a `.env` file inside the backend directory.

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Start the backend server.

```bash
uvicorn app.main:app --reload
```

Backend runs at

```
http://127.0.0.1:8000
```

Swagger documentation

```
http://127.0.0.1:8000/docs
```

---

## Frontend Setup

Navigate to the frontend folder.

```bash
cd frontend
```

Install dependencies.

```bash
npm install
```

Start the development server.

```bash
npm run dev
```

Frontend runs at

```
http://localhost:5173
```

---

## Example Queries

```
Highest paid employee

Average salary by department

Products with low stock

Top 5 customers by total purchase amount

Employees hired after 2023

Total orders placed this month
```

---

## Security

To reduce the risk of unsafe SQL execution, the backend validates every AI-generated query before execution.

Current restrictions include:

- Only SELECT statements are allowed
- Data modification statements are rejected
- Schema changes are blocked
- Potentially destructive SQL is prevented from execution

---

## Future Improvements

- Authentication and user accounts
- Multi-database support
- PostgreSQL support
- Schema-aware prompt generation
- Query optimization suggestions
- Saved queries
- Query sharing
- Database schema explorer
- Docker deployment
- Cloud deployment

---

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a new branch.

```bash
git checkout -b feature-name
```

3. Commit your changes.

```bash
git commit -m "Add new feature"
```

4. Push the branch.

```bash
git push origin feature-name
```

5. Open a Pull Request.

---
