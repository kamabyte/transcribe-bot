# 🎤 Telegram Transcribe Bot

Бот для Telegram, который превращает голосовые сообщения и аудио в текст.
Транскрибация делается через подключаемые провайдеры (по умолчанию — **Groq**,
самый дешёвый вариант с большим бесплатным лимитом).

## Возможности

- Распознаёт голосовые (`voice`), аудиофайлы (`audio`) и кружки (`video_note`)
- Текст приходит код-блоком со встроенной кнопкой копирования; длинный —
  несколькими сообщениями по лимиту Telegram
- Подключаемые провайдеры: `groq`, `openai` (легко добавить свои)
- Автоопределение языка или принудительный язык через `LANGUAGE`
- Async на `aiogram 3`

## Провайдеры

| Провайдер | Модель | Free tier | Цена |
|---|---|---|---|
| **groq** (по умолчанию) | `whisper-large-v3-turbo` | ~2000 запросов/день | $0.04/час |
| openai | `whisper-1` | нет | $0.36/час |

Ключ Groq бесплатно: https://console.groq.com/keys

## Установка

Проект управляется через [uv](https://docs.astral.sh/uv/). Python uv подтянет сам.

```bash
cd transcribe-bot
uv sync                # создаст .venv и поставит зависимости
cp .env.example .env   # затем впишите BOT_TOKEN и GROQ_API_KEY
```

Токен бота получите у [@BotFather](https://t.me/BotFather).

## Запуск

```bash
uv run transcribe-bot   # консольный скрипт
# или эквивалентно:
uv run python bot.py
```

Про запуск на сервере (Docker, Dokploy) — см. [DEPLOY.md](DEPLOY.md).

## Переключение провайдера

В `.env`:

```env
PROVIDER=openai
OPENAI_API_KEY=sk-...
```

## Как добавить новый провайдер

1. Создайте класс-наследник `TranscriptionProvider` в `providers/` и реализуйте
   `async def transcribe(self, audio, filename, language) -> str`.
2. Зарегистрируйте его в `providers/registry.py` (новая ветка в `build_provider`).

Если у сервиса OpenAI-совместимый endpoint `/audio/transcriptions` — отдельный
класс не нужен, достаточно переиспользовать `OpenAICompatibleProvider` с другим
`base_url` и `model`.

## Структура

```
transcribe-bot/
├── bot.py                  # точка входа, хендлеры aiogram
├── config.py               # настройки из .env
├── pyproject.toml          # зависимости и метаданные (uv)
├── DEPLOY.md               # деплой на сервер (Docker, Dokploy)
├── Dockerfile              # образ ghcr.io/kamabyte/transcribe-bot
├── .env.example
└── providers/
    ├── base.py             # интерфейс TranscriptionProvider
    ├── openai_compatible.py# Groq/OpenAI через openai SDK
    └── registry.py         # выбор провайдера по конфигу
```

## Лицензия

[MIT](LICENSE)
