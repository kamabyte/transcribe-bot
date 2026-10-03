# Образ бота транскрибации. Собирается GitHub Actions (.github/workflows/image.yml)
# в ghcr.io/kamabyte/transcribe-bot, запускается, например, Dokploy (см. DEPLOY.md).
#
# Состояния у бота нет: аудио скачивается и отправляется провайдеру в памяти.
# Томов не нужно. Все настройки — переменные окружения (см. .env.example),
# их задают в Dokploy → Environment.

# --- Сборка зависимостей ---------------------------------------------------
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Сначала только зависимости — слой кешируется, пока не менялся uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md bot.py config.py ./
COPY providers ./providers
RUN uv sync --frozen --no-dev

# --- Рабочий образ ---------------------------------------------------------
FROM python:3.12-slim
# Процесс не от root. uid/gid фиксированы, чтобы права не зависели от сборки.
RUN groupadd --system --gid 10001 bot && useradd --system --uid 10001 --gid bot --no-create-home bot
WORKDIR /app
COPY --from=build --chown=bot:bot /app /app
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1
USER bot
# Бот работает через long polling: портов нет, домен не нужен.
# SIGTERM aiogram обрабатывает штатно — остановка контейнера не рвёт ответ посередине.
STOPSIGNAL SIGTERM
CMD ["transcribe-bot"]
