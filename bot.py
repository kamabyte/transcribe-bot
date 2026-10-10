import asyncio
import html
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from providers import build_formatter, build_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

dp = Dispatcher()
provider = build_provider()
formatter = build_formatter()

TELEGRAM_LIMIT = 4096

# callback_data кнопки «Отформатировать». Короткая расшифровка целиком лежит
# в сообщении с кнопкой, длинная — нет, её текст берём из long_transcripts.
FORMAT = "format"
FORMAT_LONG = "format:long"

# Длинная расшифровка приходит несколькими сообщениями, а прочитать прошлые
# сообщения бот не может. Поэтому полный текст держим в памяти по ключу
# (chat_id, message_id) сообщения с кнопкой. Перезапуск бота его стирает.
long_transcripts: dict[tuple[int, int], str] = {}
LONG_TRANSCRIPTS_LIMIT = 100


def to_blocks(text: str) -> list[str]:
    """Бьёт текст на код-блоки по лимиту сообщения Telegram."""
    # Единый механизм копирования для любой длины: код-блок <pre> со
    # встроенной иконкой копирования. Нативную кнопку copy_text не используем —
    # у неё лимит Telegram в 256 символов, поэтому единого стиля с ней не выйдет.
    margin = len("<pre></pre>")
    size = TELEGRAM_LIMIT - margin
    chunks = [text[i : i + size] for i in range(0, len(text), size)]
    return [f"<pre>{html.escape(chunk)}</pre>" for chunk in chunks]


async def send_blocks(
    status: Message,
    blocks: list[str],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Пишет первый блок вместо статуса, остальные — новыми сообщениями.

    Кнопки цепляются к последнему сообщению, его и возвращает.
    """
    last = len(blocks) - 1
    await status.edit_text(blocks[0], reply_markup=reply_markup if last == 0 else None)
    sent = status
    for i, block in enumerate(blocks[1:], start=1):
        sent = await status.answer(block, reply_markup=reply_markup if i == last else None)
    return sent


def transcript_keyboard(is_long: bool) -> InlineKeyboardMarkup:
    """Кнопки под расшифровкой. Новые действия добавляются сюда."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✨ Отформатировать",
                    callback_data=FORMAT_LONG if is_long else FORMAT,
                )
            ]
        ]
    )


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

    blocks = to_blocks(text)
    is_long = len(blocks) > 1
    sent = await send_blocks(status, blocks, transcript_keyboard(is_long))
    if is_long:
        long_transcripts[(sent.chat.id, sent.message_id)] = text
        if len(long_transcripts) > LONG_TRANSCRIPTS_LIMIT:
            # dict хранит порядок вставки: первый ключ — самая старая запись.
            del long_transcripts[next(iter(long_transcripts))]


@dp.callback_query(F.data.in_({FORMAT, FORMAT_LONG}))
async def on_format(callback: CallbackQuery) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение недоступно — пришли голосовое ещё раз.", show_alert=True)
        return

    if callback.data == FORMAT_LONG:
        text = long_transcripts.get((message.chat.id, message.message_id))
    else:
        text = message.text
    if not text:
        await callback.answer(
            "Исходный текст потерян после перезапуска бота — пришли голосовое ещё раз.",
            show_alert=True,
        )
        return

    # Снимаем кнопку до запроса к модели, чтобы повторное нажатие не запустило
    # второй. При двойном нажатии второй обработчик снять её уже не сможет.
    markup = message.reply_markup
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        await callback.answer()
        return
    await callback.answer()

    status = await message.reply("✨ Форматирую…")
    try:
        formatted = await formatter.format(text)
    except Exception:  # noqa: BLE001 — показываем пользователю общую ошибку
        logger.exception("Ошибка форматирования")
        formatted = ""

    if not formatted:
        await status.edit_text("⚠️ Не удалось отформатировать текст. Попробуй ещё раз.")
        await message.edit_reply_markup(reply_markup=markup)
        return

    await send_blocks(status, to_blocks(formatted))


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
