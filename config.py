from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация бота, читается из переменных окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    provider: str = "groq"

    groq_api_key: str | None = None
    openai_api_key: str | None = None

    # Принудительный язык (ISO-639-1). Пусто -> автоопределение моделью.
    language: str | None = None

    # Модель для кнопки «Отформатировать». Пусто -> дефолтная для провайдера
    # (см. providers/registry.py).
    format_model: str | None = None

    # Кто может пользоваться ботом: Telegram ID через запятую. Пусто -> все.
    # Свой ID человек без доступа увидит в ответе бота.
    allowed_users: Annotated[frozenset[int], NoDecode] = frozenset()

    @field_validator("allowed_users", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return {int(part) for part in value.replace(" ", "").split(",") if part}
        return value


settings = Settings()
