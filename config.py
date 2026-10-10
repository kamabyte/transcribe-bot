from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
