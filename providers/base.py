from abc import ABC, abstractmethod


class TranscriptionProvider(ABC):
    """Базовый интерфейс провайдера транскрибации.

    Чтобы добавить новый провайдер: создайте подкласс, реализуйте
    transcribe() и зарегистрируйте его в providers/registry.py.
    """

    name: str = "base"

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.ogg",
        language: str | None = None,
    ) -> str:
        """Принимает байты аудио, возвращает распознанный текст."""
        raise NotImplementedError
