"""Konfiguration aus Umgebungsvariablen bzw. .env (nie im Repository, nie geloggt)."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # SecretStr: Der Schlüssel erscheint in Ausgaben und Logs nur als '**********'.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = Field(default="claude-sonnet-5-5", min_length=1)
    anthropic_model_fast: str = Field(default="claude-haiku-5-5", min_length=1)
    anthropic_model_judge: str = Field(default="claude-sonnet-5-5", min_length=1)
    # Vorläufig, bis zur Kalibrierung (Meilenstein 8): Mittelwert der Rubrik (Skala 1–5)
    judge_threshold: float = Field(default=3.5, ge=1, le=5)

    galaxus_mcp_url: str = "https://mcp.galaxus.ch"
    mcp_cache_ttl_seconds: int = 86400

    run_budget_usd: float = Field(default=0.50, gt=0)
    run_timeout_seconds: float = Field(default=180, gt=0)
    log_level: str = "INFO"

    def require_api_key(self) -> str:
        if self.anthropic_api_key is None or not self.anthropic_api_key.get_secret_value():
            raise RuntimeError("ANTHROPIC_API_KEY fehlt – in .env eintragen (siehe .env.example)")
        return self.anthropic_api_key.get_secret_value()
