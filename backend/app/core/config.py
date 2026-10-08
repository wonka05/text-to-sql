from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configuration comes from environment variables.

    Locally they are read from backend/.env; on a server they are set in the
    host's dashboard. Missing required values stop the app at startup.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Database account the app uses (the read-only user)
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # Admin account, used only by scripts/setup_db.py. Never set on the server.
    db_admin_user: str | None = None
    db_admin_password: str | None = None

    # Comma-separated frontend URLs allowed to call the API
    allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
