from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://haber:haber@db:5432/haber"
    anthropic_api_key: str = ""
    admin_password: str = "degistir-beni"

    # Çeviri yöntemi: auto (anahtar varsa Claude, yoksa ücretsiz) | claude | free
    translator: str = "auto"

    # Ücretsiz çeviri: e-posta verilirse MyMemory günlük sınırı 5.000'den 50.000 karaktere çıkar
    mymemory_email: str = ""
    # İsteğe bağlı kendi LibreTranslate sunucunuz (ör. http://libretranslate:5000); sınırsızdır
    libretranslate_url: str = ""
    libretranslate_api_key: str = ""
    # Ücretsiz servislere art arda istek arasındaki bekleme (saniye)
    free_translate_delay_seconds: float = 1.0

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
