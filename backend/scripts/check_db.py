"""Check the app's database connection: which account it uses, what that
account is allowed to do, and how many rows each table has.

Run from the backend/ folder:

    python -m scripts.check_db
"""
from sqlalchemy import inspect, text

from app.database.connection import engine


def main() -> None:
    with engine.connect() as conn:
        database = conn.execute(text("SELECT DATABASE()")).scalar()
        account = conn.execute(text("SELECT CURRENT_USER()")).scalar()
        print(f"Connected to '{database}' as {account}")

        print("Privileges:")
        for (grant,) in conn.execute(text("SHOW GRANTS")):
            print(f"  {grant}")

        print("Tables:")
        for table in inspect(conn).get_table_names():
            count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            print(f"  {table:<12} {count} rows")


if __name__ == "__main__":
    main()
