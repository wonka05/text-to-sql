import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")


def generate_sql(question: str):
    prompt = f"""
You are an expert MySQL SQL developer.

Database Schema:

Table: departments
- department_id
- department_name

Table: employees
- employee_id
- first_name
- last_name
- email
- phone
- salary
- hire_date
- department_id

Table: customers
- customer_id
- customer_name
- email
- city
- phone
- join_date

Table: products
- product_id
- product_name
- category
- price
- stock_quantity

Table: orders
- order_id
- customer_id
- order_date
- total_amount

Table: order_items
- order_item_id
- order_id
- product_id
- quantity
- unit_price

Rules:
- Return ONLY valid MySQL SQL.
- Do NOT use markdown.
- Do NOT explain anything.
- Generate only SELECT queries.

User Question:
{question}
"""

    response = model.generate_content(prompt)

    return response.text.strip()