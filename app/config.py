from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Apartello MVP"
    app_env: str = "dev"

    database_url: str

    telegram_bot_token: str
    telegram_webhook_secret: str

    travelline_webhook_secret: str | None = None
    travelline_sync_secret: str | None = None
    travelline_auth_url: str = "https://partner.tlintegration.com/auth/token"
    travelline_api_base_url: str = "https://partner.tlintegration.com/api/read-reservation"
    travelline_client_id: str | None = None
    travelline_client_secret: str | None = None
    travelline_property_ids: str | None = None
    travelline_sync_page_size: int = 100
    travelline_sync_max_pages: int = 10
    travelline_sync_lookback_minutes: int = 15

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    email_otp_secret: str = "change-me-in-env"
    email_otp_ttl_minutes: int = 10
    email_otp_attempts: int = 5
    email_otp_resend_cooldown_seconds: int = 60

    ttlock_api_base_url: str = "https://api.sciener.com"
    ttlock_client_id: str | None = None
    ttlock_client_secret: str | None = None
    ttlock_username: str | None = None
    ttlock_password_md5: str | None = None
    ttlock_timezone: str = "Europe/Amsterdam"

    access_code_mode: str = "ttlock"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def parsed_travelline_property_ids(self) -> list[str]:
        if not self.travelline_property_ids:
            return []

        values: list[str] = []
        for item in self.travelline_property_ids.split(","):
            text = item.strip()
            if text:
                values.append(text)
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
