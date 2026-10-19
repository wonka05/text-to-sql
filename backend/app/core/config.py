from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configuration comes from environment variables.

    Locally they are read from backend/.env; on a server they are set in the
    host's dashboard. Real environment variables take priority over .env.
    Missing required values stop the app at startup.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = Field(default=25, gt=0)

    # Database account the app uses (the read-only user)
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str
    # TLS for cloud MySQL (e.g. Aiven): the server's CA certificate, either a
    # file path or the PEM text itself. Empty means an unencrypted connection,
    # which is fine for a local database only.
    db_ssl_ca: str | None = None
    # Also check that the certificate matches DB_HOST
    db_ssl_verify_hostname: bool = True

    # Admin account, used only by scripts/setup_db.py. Never set on the server.
    db_admin_user: str | None = None
    db_admin_password: str | None = None

    # Limits on every query the app runs
    max_result_rows: int = Field(default=500, ge=1, le=10_000)
    query_timeout_seconds: float = Field(default=5, gt=0, le=120)
    # Comma-separated table.column pairs that may never be read, e.g.
    # "employees.salary,customers.phone"
    restricted_columns: str = ""

    # AI pipeline
    max_repair_attempts: int = Field(default=1, ge=0, le=3)
    schema_cache_seconds: int = Field(default=300, ge=0)
    generation_cache_size: int = Field(default=128, ge=0)

    # API
    # Comma-separated frontend URLs allowed to call the API
    allowed_origins: str = "http://localhost:5173"
    # Requests per minute per client IP for endpoints that run queries. 0 turns it off.
    rate_limit_per_minute: int = Field(default=20, ge=0)
    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.allowed_origins)

    @property
    def restricted_column_set(self) -> frozenset[tuple[str, str]]:
        pairs = set()
        for item in _split_csv(self.restricted_columns):
            table, _, column = item.lower().partition(".")
            if not table or not column:
                raise ValueError(
                    f"RESTRICTED_COLUMNS entry {item!r} must look like table.column"
                )
            pairs.add((table, column))
        return frozenset(pairs)


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
