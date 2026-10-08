from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.core.config import settings


def database_url(
    username: str,
    password: str,
    database: str | None = settings.db_name,
) -> URL:
    # URL.create escapes special characters (e.g. @ or /) in the password
    return URL.create(
        drivername="mysql+pymysql",
        username=username,
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
    )


engine = create_engine(
    database_url(settings.db_user, settings.db_password),
    # Cloud MySQL hosts close idle connections; test each one before use
    pool_pre_ping=True,
    pool_recycle=1800,
)
