# Apartello Backend

Backend для связки **TravelLine → FastAPI → PostgreSQL → Telegram-бот → TTLock**.

Проект предназначен для хранения бронирований, привязки гостя к Telegram-чату, показа информации по заселению и подготовленной интеграции с кодами доступа для замков.

## Текущий статус

Сейчас в проекте уже реализовано:

- приём webhook от TravelLine;
- сохранение и обновление брони в PostgreSQL;
- привязка гостя к Telegram по номеру телефона;
- подтверждение доступа через email-код;
- Telegram-меню для разделов **Моя бронь / Заселение / Проживание / Поддержка**;
- отдельный TTLock API-слой для получения списка замков, просмотра passcode'ов и генерации временного кода доступа.

Что ещё не доведено до конца:

- реальные mapping'и `property_name + room_name -> lock_id`;
- хранение выданных кодов доступа в базе;
- автоматическая выдача TTLock-кода внутри Telegram-бота вместо текстовой заглушки.

## Что умеет backend сейчас

### 1. TravelLine webhook

Backend принимает webhook от TravelLine, нормализует данные гостя и сохраняет бронь.

Поддерживается:

- поиск / создание гостя по номеру телефона;
- сохранение `external_booking_id`;
- хранение статуса, объекта, номера апартамента, дат заезда/выезда;
- сохранение исходного payload в БД.

Если у гостя уже привязан `telegram_chat_id`, backend отправляет уведомление в Telegram о том, что бронь обновилась.

### 2. Telegram-бот

Бот уже поддерживает основной сценарий гостя:

1. пользователь пишет боту;
2. отправляет телефон из бронирования;
3. система находит актуальную бронь;
4. на email из брони отправляется 6-значный код подтверждения;
5. после ввода кода Telegram-чат привязывается к гостю;
6. пользователю становятся доступны разделы по проживанию.

### 3. Контент по объекту

Через `PropertyContentService` уже отдаются:

- адрес объекта;
- инструкция по входу;
- маршрут;
- фото входа / подпись;
- Wi‑Fi;
- правила проживания;
- контакты поддержки;
- тексты для проблемных сценариев.

### 4. TTLock

В проекте уже есть техническая интеграция с TTLock:

- получение access token;
- список замков;
- список существующих клавиатурных кодов;
- генерация временного period code;
- генерация period code по `external_booking_id` брони.

Сейчас это отдельный backend-слой. В Telegram-кнопке «Показать код доступа» пока используется текстовая заглушка, а не реальный TTLock-код.

## Архитектура

```text
TravelLine webhook
        ↓
    FastAPI backend
        ↓
 PostgreSQL (guests, bookings, email_verifications)
        ↓
 Telegram bot flow
        ↓
   TTLock service layer
```

## Структура проекта

```text
apartello/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── deps.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── health.py
│   │   ├── telegram.py
│   │   ├── travelline.py
│   │   └── ttlock.py
│   └── services/
│       ├── booking_service.py
│       ├── email_service.py
│       ├── property_content_service.py
│       ├── security_service.py
│       ├── telegram_service.py
│       ├── ttlock_mapping_service.py
│       └── ttlock_service.py
├── .env.example
├── requirements.txt
└── README.md
```

## Модели данных

Сейчас в базе есть таблицы:

- `guests`
- `bookings`
- `email_verifications`

Пока **нет отдельных таблиц** для:

- замков;
- mapping'ов объект/номер → lock_id;
- выданных кодов доступа;
- истории выдачи / отзыва кодов.

## Переменные окружения

Минимально нужны:

```env
APP_NAME=Apartello MVP
APP_ENV=dev
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/apartello

TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_WEBHOOK_SECRET=replace_me
TRAVELLINE_WEBHOOK_SECRET=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=yourprojectmail@gmail.com
SMTP_PASSWORD=replace_me
SMTP_FROM_EMAIL=yourprojectmail@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false

EMAIL_OTP_SECRET=change_me_super_secret_123
EMAIL_OTP_TTL_MINUTES=10
EMAIL_OTP_ATTEMPTS=5
EMAIL_OTP_RESEND_COOLDOWN_SECONDS=60

TTLOCK_API_BASE_URL=https://api.sciener.com
TTLOCK_CLIENT_ID=
TTLOCK_CLIENT_SECRET=
TTLOCK_USERNAME=
TTLOCK_PASSWORD_MD5=
TTLOCK_TIMEZONE=Europe/Amsterdam
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

## Проверка TravelLine webhook локально

```bash
curl -X POST "http://127.0.0.1:8000/webhooks/travelline" \
  -H "Content-Type: application/json" \
  -H "X-TravelLine-Secret: <YOUR_SECRET_IF_SET>" \
  -d '{
    "booking_id": "TL-100500",
    "status": "confirmed",
    "property_name": "Apartello Tolstogo",
    "room_name": "Апартамент 12",
    "arrival_date": "2026-04-05T14:00:00",
    "departure_date": "2026-04-08T12:00:00",
    "guest": {
      "full_name": "Иван Иванов",
      "phone": "+79991234567",
      "email": "guest@example.com"
    }
  }'
```

## Настройка Telegram webhook

1. Создать бота через BotFather.
2. Подставить `TELEGRAM_BOT_TOKEN` в `.env`.
3. Поднять публичный HTTPS URL, например через ngrok.
4. Установить webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://YOUR_PUBLIC_URL/webhooks/telegram/<YOUR_TELEGRAM_WEBHOOK_SECRET>"}'
```

## TTLock endpoints

### Получить список замков

```bash
GET /ttlock/locks
```

### Получить passcode'ы конкретного замка

```bash
GET /ttlock/locks/{lock_id}/passcodes
```

### Сгенерировать временный код вручную

```bash
POST /ttlock/generate-period-code
```

### Сгенерировать временный код по брони

```bash
POST /ttlock/generate-period-code-by-booking
```

Текущий сценарий генерации по брони работает только после заполнения `LOCK_MAPPINGS` в `app/services/ttlock_mapping_service.py`.

## Важные ограничения текущей версии

- Таблицы создаются автоматически через `Base.metadata.create_all(...)`, миграций пока нет.
- README описывает текущее состояние кода, а не финальную продакшн-архитектуру.
- TTLock уже подключён на уровне backend, но ещё не встроен до конца в пользовательский Telegram-flow.
- Контент по объектам пока задаётся словарями в коде.

## Что логично сделать дальше

1. Вынести mapping замков из словаря в БД.
2. Добавить таблицу выданных кодов доступа.
3. Подключить реальный TTLock-код к кнопке «Показать код доступа» в Telegram.
4. Добавить жизненный цикл кода: выдать / показать / продлить / деактивировать.
5. Добавить Alembic и нормальные миграции.
6. Добавить аудит действий по кодам и бронированиям.

## Фокус текущего направления

Сейчас отдельное направление разработки — **locks**:

- замки;
- коды доступа;
- TTLock;
- контракт выдачи кода по брони;
- совместимость с текущим backend и сценариями Telegram-бота.