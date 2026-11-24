from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_DIR / 'uniflow.db').as_posix()}"


class Settings(BaseSettings):
    """Configurações centralizadas lidas do arquivo backend/.env."""

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    default_timezone: str = "America/Sao_Paulo"

    app_secret_key: str = "dev-secret-change-in-production"
    token_encryption_key: str = ""

    database_url: str = DEFAULT_SQLITE_URL
    frontend_origin: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"

    # Google Calendar OAuth 2.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    google_scopes: str = "https://www.googleapis.com/auth/calendar.events"

    # Webhook externo opcional (Discord / Telegram) para alertas
    alert_webhook_url: str = ""

    # Intervalos do worker (em minutos)
    google_sync_interval_minutes: int = 5
    ics_sync_interval_minutes: int = 30
    deadline_check_interval_minutes: int = 5

    # Conta inicial
    admin_email: str = "estudante@uniflow.local"
    admin_password: str = "uniflow123"
    admin_name: str = "Estudante UniFlow"

    # Sessão e limites HTTP
    session_ttl_hours: int = 24 * 14  # 14 dias
    http_timeout_seconds: float = 15.0
    ics_max_bytes: int = 5 * 1024 * 1024  # 5 MB

    def resolved_database_url(self) -> str:
        """Garante caminho absoluto no SQLite para API e Worker compartilharem o mesmo arquivo."""
        url = self.database_url.strip()
        if url.startswith("sqlite:///./"):
            rel = url.removeprefix("sqlite:///./")
            return f"sqlite:///{(BACKEND_DIR / rel).as_posix()}"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
