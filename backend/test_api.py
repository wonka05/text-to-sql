
from app.services.ai_service import generate_sql

question = "Show employees earning more than 80000"

print(generate_sql(question))