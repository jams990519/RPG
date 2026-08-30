"""Configuración del bot usando pydantic-settings."""
import sys
from typing import Annotated, Any, List

from loguru import logger
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central del bot.

    Todos los valores se leen del entorno o del archivo `.env`.
    """

    # Telegram
    bot_token: str = ""
    admin_ids: Annotated[List[int], NoDecode] = []

    # Database
    database_url: str = "sqlite:///bot_database.db"

    # Game config
    daily_coins: int = 100
    min_bet: int = 10
    max_bet: int = 10000
    cooldown_seconds: int = 3
    start_coins: int = 500

    # Logging
    log_level: str = "INFO"
    log_file: str = "bot.log"

    # Environment
    environment: str = "development"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: Any) -> List[int]:
        """Acepta `1,2,3`, `[1, 2]` o una lista ya construida."""
        if value is None or value == "":
            return []
        if isinstance(value, (list, tuple, set)):
            return [int(item) for item in value]
        if isinstance(value, int):
            return [value]
        raw = str(value).strip().strip("[]")
        return [int(part) for part in raw.replace(";", ",").split(",") if part.strip()]

    @property
    def async_database_url(self) -> str:
        """Traduce la URL a su driver asíncrono equivalente."""
        url = self.database_url
        if url.startswith("sqlite+") or url.startswith("postgresql+"):
            return url
        if url.startswith("sqlite:"):
            return url.replace("sqlite:", "sqlite+aiosqlite:", 1)
        if url.startswith("postgresql:"):
            return url.replace("postgresql:", "postgresql+asyncpg:", 1)
        if url.startswith("postgres:"):
            return url.replace("postgres:", "postgresql+asyncpg:", 1)
        return url

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


settings = Settings()


def setup_logging() -> None:
    """Configurar el sistema de logging."""
    logger.remove()

    # Consola
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # Archivo
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=settings.log_level,
    )

    logger.info(f"📝 Logging configurado - Nivel: {settings.log_level}")
