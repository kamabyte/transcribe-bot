from config import settings

from .base import TranscriptionProvider
from .formatter import TextFormatter
from .openai_compatible import OpenAICompatibleProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_provider() -> TranscriptionProvider:
    """Создаёт провайдер по настройке settings.provider.

    Новый провайдер добавляется одной веткой здесь (или своим классом,
    наследующим TranscriptionProvider).
    """
    name = settings.provider.lower()

    if name == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("PROVIDER=groq, но GROQ_API_KEY не задан")
        return OpenAICompatibleProvider(
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            model="whisper-large-v3-turbo",
            name="groq",
        )

    if name == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("PROVIDER=openai, но OPENAI_API_KEY не задан")
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=None,  # дефолтный endpoint OpenAI
            model="whisper-1",
            name="openai",
        )

    raise RuntimeError(f"Неизвестный PROVIDER: {settings.provider!r}")


def build_formatter() -> TextFormatter:
    """Создаёт форматтер текста для кнопки «Отформатировать».

    Работает на ключе того же провайдера, что и транскрибация. Модель —
    из FORMAT_MODEL, иначе дефолтная для провайдера.
    """
    name = settings.provider.lower()

    if name == "groq" and settings.groq_api_key:
        return TextFormatter(
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            model=settings.format_model or "openai/gpt-oss-120b",
        )

    if name == "openai" and settings.openai_api_key:
        return TextFormatter(
            api_key=settings.openai_api_key,
            base_url=None,  # дефолтный endpoint OpenAI
            model=settings.format_model or "gpt-5-mini",
        )

    raise RuntimeError(f"Нет ключа для форматирования (PROVIDER={settings.provider!r})")
