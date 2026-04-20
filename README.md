# Apartello Backend MVP

Backend для связки **TravelLine → FastAPI → PostgreSQL → Telegram-бот**.

Текущая ветка ориентирована на **hybrid-интеграцию с TravelLine**:

- **Read Reservation API** — основной канал синхронизации броней;
- **webhook** — опциональный ускоритель синхронизации, если у объекта позже появится WebPMS;
- Telegram-авторизация — по кнопке **«Поделиться моим номером»**;
- тестовый код доступа — **последние 4 цифры телефона гостя**, если номер телефона уже есть в системе.

---

## Почему теперь API-first

По официальной документации TravelLine:

- `Read Reservation API` позволяет читать бронирования из **TL: Booking Engine, TL: Channel Manager и TL: WebPMS**;
- webhook-события сейчас публикует **только WebPMS**;
- в webhook `payload` не допускаются персональные данные;
- детали брони в `Read Reservation API` содержат номер брони, статус, даты, room stays, тарифы и пр., но без WebPMS телефон/email гостя могут отсутствовать.

Из-за этого текущий план такой:

1. **без WebPMS** — работаем через API polling;
2. **с WebPMS** — добавляем webhook как быстрый триггер sync;
3. во всех случаях **источник истины по брони — API sync**, а не webhook-пакет.

---

## Что уже поддерживает эта версия

### Telegram
- вход через кнопку `request_contact`;
- проверка, что отправлен **свой** контакт Telegram;
- поиск брони по номеру телефона;
- привязка `telegram_chat_id` к гостю;
- разделы:
  - **Моя бронь**
  - **Заселение**
  - **Проживание**
  - **Поддержка**

### TravelLine
- legacy webhook с полной бронью всё ещё поддерживается;
- официальный webhook с пакетами событий поддерживается как **триггер API-sync**;
- ручной sync последних броней через backend endpoint;
- ручной sync конкретной брони через backend endpoint;
- мягкая обработка аномальных legacy payload;
- понятные логи по webhook и sync.

### Доступ
- тестовый код доступа: `ACCESS_CODE_MODE=phone_last4`;
- если номера телефона у гостя нет, код в тестовом режиме недоступен.

---

## Структура проекта

```text
apartello/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── deps.py
│   ├── models.py
│   ├── routers/
│   │   ├── health.py
│   │   ├── telegram.py
│   │   ├── travelline.py
│   │   └── ttlock.py
│   └── services/
│       ├── access_code_service.py
│       ├── booking_service.py
│       ├── property_content_service.py
│       ├── telegram_service.py
│       ├── travelline_api_service.py
│       ├── travelline_models.py
│       └── travelline_sync_service.py
├── .env.example
└── README.md
```

---

## Что заменить / добавить

### Заменить
- `app/config.py`
- `app/services/booking_service.py`
- `app/routers/travelline.py`
- `README.md`
- `.env.example`

### Добавить
- `app/services/travelline_models.py`
- `app/services/travelline_api_service.py`
- `app/services/travelline_sync_service.py`

---

## Новые переменные окружения

```env
APP_NAME=Apartello MVP
APP_ENV=dev

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/apartello

TELEGRAM_BOT_TOKEN=123456:replace_me
TELEGRAM_WEBHOOK_SECRET=super-secret-path

TRAVELLINE_WEBHOOK_SECRET=
TRAVELLINE_SYNC_SECRET=
TRAVELLINE_AUTH_URL=https://partner.tlintegration.com/auth/token
TRAVELLINE_API_BASE_URL=https://partner.tlintegration.com/api/read-reservation
TRAVELLINE_CLIENT_ID=
TRAVELLINE_CLIENT_SECRET=
TRAVELLINE_PROPERTY_IDS=
TRAVELLINE_SYNC_PAGE_SIZE=100
TRAVELLINE_SYNC_MAX_PAGES=10
TRAVELLINE_SYNC_LOOKBACK_MINUTES=15

ACCESS_CODE_MODE=phone_last4
```

### Что означают новые поля
- `TRAVELLINE_CLIENT_ID`, `TRAVELLINE_CLIENT_SECRET` — доступ к Read Reservation API;
- `TRAVELLINE_PROPERTY_IDS` — список property id через запятую;
- `TRAVELLINE_SYNC_SECRET` — опциональная защита ручных sync endpoint;
- `TRAVELLINE_WEBHOOK_SECRET` — опциональная защита webhook endpoint;
- `ACCESS_CODE_MODE=phone_last4` — тестовый код доступа как последние 4 цифры телефона.

---

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
source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
```

### 3. Запустить backend

```bash
python -m uvicorn app.main:app --reload
```

### 4. Проверить health

```bash
curl http://127.0.0.1:8000/health
```

---

## Настройка Telegram webhook

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://YOUR_PUBLIC_URL/webhooks/telegram/super-secret-path"}'
```

---

## Как тестировать TravelLine без WebPMS

### Вариант A — ручной sync последних броней

```bash
curl -X POST "http://127.0.0.1:8000/webhooks/travelline/sync/recent"
```

Если задан `TRAVELLINE_SYNC_SECRET`:

```bash
curl -X POST "http://127.0.0.1:8000/webhooks/travelline/sync/recent" \
  -H "x-travelline-sync-secret: YOUR_SECRET"
```

### Вариант B — ручной sync одной брони

```bash
curl -X POST "http://127.0.0.1:8000/webhooks/travelline/sync/booking/<PROPERTY_ID>/<BOOKING_NUMBER>"
```

---

## Как использовать webhook позже

Если у объекта появится WebPMS, можно подключить webhook на:

```text
POST /webhooks/travelline
```

В этой версии backend уже умеет:
- принимать legacy payload с полной бронью;
- принимать пакет событий webhook;
- использовать webhook как триггер, а затем подтягивать детали брони через API.

---

## Ограничения текущей hybrid-версии

- без WebPMS телефон и email гостя могут не приходить из TravelLine;
- без телефона Telegram-авторизация гостя по номеру работать не сможет;
- тестовый код `phone_last4` тоже зависит от того, есть ли телефон;
- polling пока запускается вручную endpoint-ами, а не фоновым scheduler.

---

## Текущий план

### Этап 1
Стабилизировать **API-first sync**:
- получить список броней через `Read Reservation API`;
- сохранять/обновлять брони в БД;
- использовать polling как основной канал.

### Этап 2
Поддержать реальные объекты без WebPMS:
- проверять, какие поля реально приходят по конкретному отелю;
- оценить, хватает ли их для Telegram-сценария;
- при необходимости добавлять email onboarding или другой канал идентификации.

### Этап 3
Подключить webhook как ускоритель:
- если у клиента появится WebPMS;
- если TravelLine начнёт присылать события брони;
- webhook остаётся быстрым триггером для sync, а не источником guest PII.

### Этап 4
После этого уже возвращаться к:
- TTLock production flow;
- email onboarding;
- админке;
- scheduler для регулярного polling.
