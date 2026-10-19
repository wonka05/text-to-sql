import re
import tempfile
from pathlib import Path

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


def _normalize_pem(text: str) -> str:
    """Rebuild PEM line breaks, which pasting into a one-line field can remove."""
    blocks = re.findall(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", text, re.DOTALL)
    out = []
    for label, body in blocks:
        b64 = "".join(body.split())
        lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
        out.append("\n".join([f"-----BEGIN {label}-----", *lines, f"-----END {label}-----"]))
    return "\n".join(out) + "\n"


def ssl_connect_args(settings: Settings) -> dict:
    """PyMySQL arguments that turn on TLS with certificate verification."""
    ca = (settings.db_ssl_ca or "").strip()
    if not ca:
        return {}
    if ca.startswith("-----BEGIN"):
        # Hosting dashboards make it easier to paste the PEM text than to
        # upload a file, so write it to a file for the driver
        path = Path(tempfile.gettempdir()) / "querent-db-ca.pem"
        path.write_text(_normalize_pem(ca), encoding="ascii")
        ca = str(path)
    return {
        "ssl_ca": ca,
        "ssl_verify_cert": True,
        "ssl_verify_identity": settings.db_ssl_verify_hostname,
    }


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
            **ssl_connect_args(settings),
        },
    )

    @event.listens_for(engine, "connect")
    def _configure_session(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            # Applies to SELECT statements; MySQL aborts them with error 3024
            cursor.execute(f"SET SESSION max_execution_time = {timeout_ms}")

    return engine
