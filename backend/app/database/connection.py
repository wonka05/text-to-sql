from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine

from app.core.config import Settings


def database_url(
    settings: Settings,
    username: str,
    password: str,
    database: str | None,
) -> URL:
    # URL.create escapes special characters (e.g. @ or /) in the password
    return URL.create(
        drivername="mysql+pymysql",
        username=username,
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
        query={"charset": "utf8mb4"},
    )


def create_query_engine(settings: Settings) -> Engine:
    """Engine for everything the app reads, including generated queries.

    Every pooled connection is put into a read-only session with a statement
    time limit, so even a query that slipped past the SQL guard could not
    write or run for long. This sits on top of the database account having
    only SELECT privileges.
    """
    timeout_ms = int(settings.query_timeout_seconds * 1000)

    engine = create_engine(
        database_url(settings, settings.db_user, settings.db_password, settings.db_name),
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        # Cloud MySQL hosts close idle connections; test each one before use
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": 5,
            # Backstop in case the server-side limit never fires (e.g. network hang)
            "read_timeout": int(settings.query_timeout_seconds) + 10,
            "write_timeout": 10,
        },
    )

    @event.listens_for(engine, "connect")
    def _configure_session(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            # Applies to SELECT statements; MySQL aborts them with error 3024
            cursor.execute(f"SET SESSION max_execution_time = {timeout_ms}")

    return engine
