from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://haber:haber@db:5432/haber"
    anthropic_api_key: str = ""
    admin_password: str = "degistir-beni"

    # Modeller: ucuz ayıklama + kaliteli Türkçeleştirme
    relevance_model: str = "claude-haiku-4-5"
    rewrite_model: str = "claude-sonnet-5"

    # Bütçe (EUR). Yapay zekâ bütçesi = aylık sınır - sunucu maliyeti
    monthly_budget_eur: float = 50.0
    server_cost_eur: float = 10.0
    usd_to_eur: float = 0.92
    budget_warning_ratio: float = 0.8

    scan_interval_minutes: int = 60
    scheduler_enabled: bool = True
    request_timeout_seconds: float = 20.0
    max_items_per_source: int = 30

    @property
    def ai_budget_eur(self) -> float:
        return max(self.monthly_budget_eur - self.server_cost_eur, 0.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
