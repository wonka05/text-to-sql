from app.database.connection import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DATABASE();"))
        print("Connected Successfully!")
        print(result.fetchone())

except Exception as e:
    print(e)