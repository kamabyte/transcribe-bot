from config import settings

from .base import TranscriptionProvider
from .openai_compatible import OpenAICompatibleProvider


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
            base_url="https://api.groq.com/openai/v1",
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
