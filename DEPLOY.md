# Деплой на сервер

Бот запускается как Docker-контейнер из образа `ghcr.io/kamabyte/transcribe-bot`.
Образ собирает GitHub Actions на каждый push в `main`. Ниже — пример для **Dokploy**;
подойдёт и любой другой способ запустить контейнер (`docker run`, Compose).

    push в main ──► GitHub Actions ──► ghcr.io/kamabyte/transcribe-bot:{sha-…, latest}
                                                 │
                                    Dokploy ── Deploy ──► контейнер

## Что нужно боту

| | |
|---|---|
| Порты, домен | нет: long polling к `api.telegram.org` |
| Тома | нет: аудио обрабатывается в памяти |
| Переменные | `BOT_TOKEN`, `PROVIDER` (`groq`), `GROQ_API_KEY`; опционально `OPENAI_API_KEY`, `LANGUAGE` — см. `.env.example` |
| Ресурсы | 1 ядро и 512 МБ хватает с запасом |
| Экземпляров | **ровно один**: два процесса на одном токене Telegram мешают друг другу (`Conflict: terminated by other getUpdates`) |

## Без Dokploy

```bash
docker run -d --name transcribe-bot --restart unless-stopped \
  --env-file .env ghcr.io/kamabyte/transcribe-bot:latest
```

## Установка в Dokploy

1. Образ собран: во вкладке Actions репозитория зелёный `image`, в Packages есть
   `transcribe-bot`.
2. Dokploy → проект → **Create Service → Application**, например `transcribe`.
3. **General → Provider: Docker.** Image `ghcr.io/kamabyte/transcribe-bot:latest`
   (или свой форк). Для приватного образа — Registry `ghcr.io` с токеном `read:packages`.
4. **Environment** — переменные из таблицы выше. Значения в репозиторий не класть.
5. **Advanced → Resources:** CPU limit 1, memory limit 512 MB.
6. Домен не добавлять.
7. **Deploy.** Если бот на этом токене уже где-то запущен — сначала остановите его там.
8. Проверка: в логах приложения — `Бот запущен. Провайдер: groq`;
   голосовое в Telegram — приходит текст.

## Обновление

Push в `main` → Actions собирает новый образ → в Dokploy у приложения **Deploy**.
Надёжнее указывать конкретный тег `sha-<коммит>`, а не `latest`: тогда Dokploy
гарантированно скачает новый образ. Откат — Deployments → предыдущий деплой,
либо прежний тег `sha-<коммит>` и Deploy.

## Частые проблемы

| Симптом | Причина |
|---|---|
| `Conflict: terminated by other getUpdates request` | работают два экземпляра на одном токене: старый запуск не остановлен или больше одной реплики |
| `pull access denied` при Deploy | образ приватный, а в Dokploy не выбран реестр `ghcr.io` или у токена нет `read:packages` |
| `ValidationError: bot_token` при старте | не задана переменная `BOT_TOKEN` в Environment |
| Бот молчит, в логах ошибки Groq | лимит бесплатного ключа (~2000 запросов в день) или ключ отозван |
