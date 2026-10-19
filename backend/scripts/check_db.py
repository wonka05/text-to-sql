"""Check the app's database connection: which account it uses, what that
account is allowed to do, how many rows each table has, and the schema the
assistant will see.

Run from the backend/ folder:

    python -m scripts.check_db
"""
from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.database.connection import create_query_engine
from app.services.catalog import load_catalog
from app.services.prompts import render_schema


def main() -> None:
    settings = get_settings()
    engine = create_query_engine(settings)

    with engine.connect() as conn:
        database = conn.execute(text("SELECT DATABASE()")).scalar()
        account = conn.execute(text("SELECT CURRENT_USER()")).scalar()
        print(f"Connected to '{database}' as {account}")

        read_only = conn.execute(text("SELECT @@transaction_read_only")).scalar()
        timeout = conn.execute(text("SELECT @@max_execution_time")).scalar()
        print(f"Session: read-only={bool(read_only)}, statement time limit={timeout} ms")

        print("Privileges:")
        for (grant,) in conn.execute(text("SHOW GRANTS")):
            print(f"  {grant}")

        print("Tables:")
        for table in inspect(conn).get_table_names():
            count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            print(f"  {table:<12} {count} rows")

    catalog = load_catalog(engine, settings.db_name, settings.restricted_column_set)
    print(f"\nSchema the model sees (fingerprint {catalog.fingerprint}):\n")
    print(render_schema(catalog))
    engine.dispose()


if __name__ == "__main__":
    main()
