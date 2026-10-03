from io import BytesIO

from openai import AsyncOpenAI

from .base import TranscriptionProvider


class OpenAICompatibleProvider(TranscriptionProvider):
    """Провайдер для любого OpenAI-совместимого audio API.

    Подходит и для OpenAI, и для Groq (у Groq endpoint
    https://api.groq.com/openai/v1 полностью совместим с
    /audio/transcriptions). Отличаются только base_url, ключ и модель.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        name: str = "openai-compatible",
    ):
        self.name = name
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.ogg",
        language: str | None = None,
    ) -> str:
        # SDK ждёт file-like объект с именем (имя задаёт расширение/формат).
        file_obj = BytesIO(audio)
        file_obj.name = filename

        kwargs: dict = {"model": self.model, "file": file_obj}
        if language:
            kwargs["language"] = language

        result = await self._client.audio.transcriptions.create(**kwargs)
        return result.text.strip()
