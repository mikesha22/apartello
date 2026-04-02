# Apartello Backend MVP

Минимальный backend на Python для связки **TravelLine → FastAPI → PostgreSQL → Telegram-бот**.

## Что умеет MVP

- принимает webhook от TravelLine;
- сохраняет бронь в PostgreSQL;
- принимает webhook от Telegram;
- отправляет сообщения пользователю в Telegram;
- умеет привязать Telegram-чат к гостю по номеру телефона.

## Стек

- FastAPI
- PostgreSQL
- SQLAlchemy
- httpx
- Telegram Bot API

## Структура

```text
apartello_backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── deps.py
│   ├── routers/
│   │   ├── health.py
│   │   ├── telegram.py
│   │   └── travelline.py
│   └── services/
│       ├── booking_service.py
│       └── telegram_service.py
├── .env.example
├── requirements.txt
└── README.md
```

## Локальный запуск

### 1. Поднять PostgreSQL

```bash
docker run --name apartello-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=apartello \
  -p 5432:5432 \
  -d postgres:17
```

### 2. Установить зависимости

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Запустить приложение

```bash
uvicorn app.main:app --reload
```

## Проверка healthcheck

```bash
curl http://127.0.0.1:8000/health
```

## Настройка Telegram webhook

1. Создай бота через BotFather.
2. Подставь `TELEGRAM_BOT_TOKEN` в `.env`.
3. Подними публичный HTTPS URL, например через ngrok.
4. Установи webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://YOUR_PUBLIC_URL/webhooks/telegram/super-secret-path"}'
```

## Проверка TravelLine webhook локально

```bash
curl -X POST "http://127.0.0.1:8000/webhooks/travelline" \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": "TL-100500",
    "status": "confirmed",
    "property_name": "Apartello Tolstogo",
    "room_name": "Апартамент 12",
    "arrival_date": "2026-04-05T14:00:00",
    "departure_date": "2026-04-08T12:00:00",
    "guest": {
      "full_name": "Иван Иванов",
      "phone": "+79991234567"
    }
  }'
```

## Дальше логично добавить

- Alembic
- Docker Compose
- таблицу `booking_events`
- нормальную схему под реальный payload TravelLine
- deep link `/start <token>`
- интеграцию с кодами замков
