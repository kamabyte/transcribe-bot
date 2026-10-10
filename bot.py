import asyncio
import html
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
    User,
)

from config import settings
from providers import build_formatter, build_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

dp = Dispatcher()
provider = build_provider()
formatter = build_formatter()

TELEGRAM_LIMIT = 4096
BLOCK_SIZE = TELEGRAM_LIMIT - len("<pre></pre>")

# callback_data кнопок под расшифровкой. FORMAT_LONG — у расшифровки из
# нескольких сообщений: после перезапуска бота её текст не восстановить,
# а короткая лежит в сообщении с кнопкой целиком.
FORMAT = "format"
FORMAT_LONG = "format:long"
ORIGINAL = "original"
BUSY = "busy"

LOST = "Текст потерян после перезапуска бота — пришли голосовое ещё раз."


@dataclass
class Transcript:
    """Расшифровка и сообщения, в которых она показана (кнопка — на последнем)."""

    original: str
    message_ids: list[int]
    formatted: str | None = None


# Оригинал и отформатированный текст показываются в одних и тех же сообщениях
# по очереди, а прочитать прошлые сообщения бот не может. Поэтому расшифровки
# держим в памяти по ключу (chat_id, message_id) сообщения с кнопкой.
# Перезапуск бота их стирает.
transcripts: dict[tuple[int, int], Transcript] = {}
TRANSCRIPTS_LIMIT = 200


@dp.message.outer_middleware()
@dp.callback_query.outer_middleware()
async def check_access(
    handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: dict[str, Any],
) -> Any:
    """Пускает к хендлерам только пользователей из ALLOWED_USERS (пусто — всех).

    Остальным бот отвечает их ID: владелец добавит его, если захочет дать доступ.
    """
    user: User | None = data.get("event_from_user")
    if not settings.allowed_users or (user and user.id in settings.allowed_users):
        return await handler(event, data)

    if user is None:
        return None
    logger.info("Нет доступа: id=%s @%s", user.id, user.username)
    if isinstance(event, Message):
        await event.answer(
            "🔒 Это личный бот.\n\n"
            f"Твой Telegram ID: <code>{user.id}</code> — передай его владельцу, если нужен доступ."
        )
    elif isinstance(event, CallbackQuery):
        await event.answer("🔒 Нет доступа", show_alert=True)
    return None


def to_blocks(text: str, count: int = 1) -> list[str]:
    """Бьёт текст поровну на код-блоки: не меньше count и не длиннее лимита Telegram.

    Поровну — чтобы отформатированный текст, обычно более короткий, занял
    те же сообщения, что и оригинал.
    """
    # Единый механизм копирования для любой длины: код-блок <pre> со
    # встроенной иконкой копирования. Нативную кнопку copy_text не используем —
    # у неё лимит Telegram в 256 символов, поэтому единого стиля с ней не выйдет.
    count = max(count, -(-len(text) // BLOCK_SIZE))
    bounds = [len(text) * i // count for i in range(count + 1)]
    return [f"<pre>{html.escape(text[a:b])}</pre>" for a, b in zip(bounds, bounds[1:])]


def keyboard(text: str, data: str) -> InlineKeyboardMarkup:
    """Кнопка под расшифровкой."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)]])


def format_keyboard(is_long: bool, text: str = "✨ Отформатировать") -> InlineKeyboardMarkup:
    return keyboard(text, FORMAT_LONG if is_long else FORMAT)


def remember(chat_id: int, t: Transcript) -> None:
    transcripts[(chat_id, t.message_ids[-1])] = t
    if len(transcripts) > TRANSCRIPTS_LIMIT:
        # dict хранит порядок вставки: первый ключ — самая старая запись.
        del transcripts[next(iter(transcripts))]


async def show(bot: Bot, chat_id: int, t: Transcript, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    """Показывает text в сообщениях расшифровки, кнопку — на последнем.

    Если текст не влезает в прежние сообщения, недостающие дописываются в конец чата.
    """
    blocks = to_blocks(text, len(t.message_ids))
    for i, block in enumerate(blocks):
        markup = reply_markup if i == len(blocks) - 1 else None
        if i == len(t.message_ids):
            sent = await bot.send_message(chat_id, block, reply_markup=markup)
            t.message_ids.append(sent.message_id)
            continue
        try:
            await bot.edit_message_text(block, chat_id=chat_id, message_id=t.message_ids[i], reply_markup=markup)
        except TelegramBadRequest as e:
            # Этот кусок уже показан ровно таким — не ошибка
            if "message is not modified" not in e.message:
                raise
    remember(chat_id, t)


async def callback_message(callback: CallbackQuery) -> Message | None:
    """Сообщение с нажатой кнопкой; None — если боту оно уже недоступно."""
    if isinstance(callback.message, Message):
        return callback.message
    await callback.answer("Сообщение недоступно — пришли голосовое ещё раз.", show_alert=True)
    return None


async def drop_buttons(callback: CallbackQuery, message: Message) -> None:
    """Без расшифровки в памяти кнопка уже не сработает — убираем её."""
    await callback.answer(LOST, show_alert=True)
    with suppress(TelegramBadRequest):
        await message.edit_reply_markup(reply_markup=None)


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

    # Статус становится первым сообщением расшифровки
    t = Transcript(text, [status.message_id])
    await show(bot, message.chat.id, t, text, format_keyboard(len(text) > BLOCK_SIZE))


@dp.callback_query(F.data.in_({FORMAT, FORMAT_LONG}))
async def on_format(callback: CallbackQuery, bot: Bot) -> None:
    message = await callback_message(callback)
    if message is None:
        return
    t = transcripts.get((message.chat.id, message.message_id))
    if t is None and callback.data == FORMAT and message.text:
        # Бот перезапускался, но короткая расшифровка целиком в сообщении
        t = Transcript(message.text, [message.message_id])
        remember(message.chat.id, t)
    if t is None:
        await drop_buttons(callback, message)
        return

    if t.formatted is None:
        # «⏳» — и индикатор, и защита от двойного нажатия: второй обработчик
        # поставить ту же кнопку уже не сможет.
        try:
            await message.edit_reply_markup(reply_markup=keyboard("⏳ Форматирую…", BUSY))
        except TelegramBadRequest:
            await callback.answer()
            return
        await callback.answer()

        try:
            formatted = await formatter.format(t.original)
        except Exception:  # noqa: BLE001 — пользователю хватит кнопки «ещё раз»
            logger.exception("Ошибка форматирования")
            formatted = ""
        # Пустой ответ — сбой. Заодно в каждое сообщение нужен хотя бы символ.
        if len(formatted) < len(t.message_ids):
            await message.edit_reply_markup(
                reply_markup=format_keyboard(len(t.message_ids) > 1, "⚠️ Не вышло — ещё раз")
            )
            return
        t.formatted = formatted
    else:
        await callback.answer()

    await show(bot, message.chat.id, t, t.formatted, keyboard("↩️ Оригинал", ORIGINAL))


@dp.callback_query(F.data == ORIGINAL)
async def on_original(callback: CallbackQuery, bot: Bot) -> None:
    message = await callback_message(callback)
    if message is None:
        return
    t = transcripts.get((message.chat.id, message.message_id))
    if t is None:
        await drop_buttons(callback, message)
        return
    await callback.answer()
    await show(bot, message.chat.id, t, t.original, format_keyboard(len(t.message_ids) > 1))


@dp.callback_query(F.data == BUSY)
async def on_busy(callback: CallbackQuery) -> None:
    message = await callback_message(callback)
    if message is None:
        return
    if (message.chat.id, message.message_id) not in transcripts:
        # Бот перезапустился посреди форматирования
        await drop_buttons(callback, message)
        return
    await callback.answer("⏳ Уже форматирую…")


@dp.message()
async def on_other(message: Message) -> None:
    await message.answer("Пришли голосовое сообщение или аудиофайл 🎤")


async def main() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Бот запущен. Провайдер: %s", provider.name)
    if settings.allowed_users:
        logger.info("Доступ ограничен: ALLOWED_USERS (записей: %d)", len(settings.allowed_users))
    else:
        logger.warning("ALLOWED_USERS пуст — ботом может пользоваться любой")
    await dp.start_polling(bot)


def run() -> None:
    """Точка входа для консольного скрипта (uv run transcribe-bot)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
