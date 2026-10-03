import asyncio
import html
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import settings
from providers import build_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

dp = Dispatcher()
provider = build_provider()

TELEGRAM_LIMIT = 4096


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Пришли мне голосовое сообщение или аудио — я расшифрую его в текст.\n\n"
        f"Сейчас используется провайдер: <b>{provider.name}</b>"
    )


@dp.message(F.voice | F.audio | F.video_note)
async def on_voice(message: Message, bot: Bot) -> None:
    # У разных типов сообщений объект файла лежит в разных полях.
    media = message.voice or message.audio or message.video_note
    if media is None:
        return

    status = await message.answer("🎧 Распознаю…")

    try:
        buffer = BytesIO()
        await bot.download(media, destination=buffer)
        audio_bytes = buffer.getvalue()

        text = await provider.transcribe(
            audio_bytes,
            filename="audio.ogg",
            language=settings.language or None,
        )
    except Exception:  # noqa: BLE001 — показываем пользователю общую ошибку
        logger.exception("Ошибка транскрибации")
        await status.edit_text("⚠️ Не удалось распознать аудио. Попробуй ещё раз.")
        return

    if not text:
        await status.edit_text("🤔 Не удалось распознать речь — тишина или шум?")
        return

    # Единый механизм копирования для любой длины: код-блок <pre> со
    # встроенной иконкой копирования. Нативную кнопку copy_text не используем —
    # у неё лимит Telegram в 256 символов, поэтому единого стиля с ней не выйдет.
    # Длинный текст бьём на куски по лимиту сообщения Telegram.
    margin = len("<pre></pre>")
    size = TELEGRAM_LIMIT - margin
    chunks = [text[i : i + size] for i in range(0, len(text), size)]
    blocks = [f"<pre>{html.escape(chunk)}</pre>" for chunk in chunks]
    await status.edit_text(blocks[0])
    for block in blocks[1:]:
        await message.answer(block)


@dp.message()
async def on_other(message: Message) -> None:
    await message.answer("Пришли голосовое сообщение или аудиофайл 🎤")


async def main() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Бот запущен. Провайдер: %s", provider.name)
    await dp.start_polling(bot)


def run() -> None:
    """Точка входа для консольного скрипта (uv run transcribe-bot)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
