"""Konfiguration aus Umgebungsvariablen und .env."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zugangsdaten und Verbindungsparameter der Nextcloud-Instanz."""

    model_config = SettingsConfigDict(
        env_prefix="ADFC_NC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = Field(default="https://by.adfc-clouds.de")
    admin_user: str
    admin_password: str
    share_user: str = "OCMaster_LV_Nextcloud"
    share_password: str = ""
    verify_tls: bool = True
    timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 3600
    state_dir: Path = Field(default=Path(".adfc-nc"))
    resource_user_prefix: str = "OC"


def load_settings() -> Settings:
    """Lädt die Einstellungen aus Umgebung und .env."""
    return Settings()
