# Apartello Backend MVP

Минимальный backend на Python для связки:

**TravelLine → FastAPI → PostgreSQL → Telegram-бот**

Текущая версия проекта ориентирована на сценарий, где после бронирования гость переходит в Telegram-бота и **идентифицируется через кнопку Telegram "Поделиться моим номером"**. После этого бот ищет бронь по номеру телефона и открывает гостю информацию по проживанию.

## Что умеет текущий MVP

- принимает webhook от TravelLine;
- сохраняет бронь и гостя в PostgreSQL;
- принимает webhook от Telegram;
- привязывает Telegram-чат к гостю по **собственному номеру телефона**, отправленному через кнопку `request_contact`;
- показывает карточку брони;
- показывает разделы:
  - **Моя бронь**
  - **Заселение**
  - **Проживание**
  - **Поддержка**
- поддерживает inline-кнопки внутри разделов;
- позволяет вынести адрес, Wi‑Fi, инструкции, правила и контакты поддержки в отдельный конфиг по объектам.

## Что важно по логике авторизации

Сейчас мы **не используем обязательную email-верификацию** для входа в бота.

Текущий вход работает так:

1. Пользователь нажимает `/start`.
2. Если чат еще не привязан, бот показывает кнопку **«Поделиться моим номером»**.
3. Telegram отправляет контакт пользователя.
4. Backend проверяет, что это **именно контакт самого пользователя**, а не чужой номер.
5. Backend ищет бронь по номеру телефона.
6. Если бронь найдена — чат привязывается к гостю, и бот открывает доступ к информации.

## Стек

- FastAPI
- PostgreSQL
- SQLAlchemy
- httpx
- Telegram Bot API

## Структура проекта

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
│       ├── property_content_service.py
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
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

### 3. Запустить приложение

```bash
python -m uvicorn app.main:app --reload
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

## Как протестировать авторизацию через контакт

### 1. Отправь тестовую бронь в webhook TravelLine

Пример payload должен содержать номер телефона гостя:

```json
{
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
}
```

### 2. Открой бота и отправь `/start`

Если чат еще не привязан, бот предложит нажать кнопку:

**Поделиться моим номером**

### 3. Отправь свой контакт через кнопку Telegram

Бот:
- проверит, что это именно твой контакт;
- найдет бронь по номеру;
- привяжет `telegram_chat_id`;
- откроет доступ к разделам.

## Где редактировать контент по объектам

Файл:

```text
app/services/property_content_service.py
```

Там можно менять:
- адреса объектов;
- инструкции по заселению;
- Wi‑Fi;
- правила проживания;
- телефоны поддержки;
- Telegram / WhatsApp;
- ссылки на карты.

## Ограничения текущей версии

- код доступа пока отдается как заглушка;
- нет полноценной интеграции с TTLock в основном пользовательском потоке;
- нет отдельной админки;
- email после webhook можно использовать как канал onboarding позже, но он **не обязателен** для текущей авторизации в боте.

## Ближайшие шаги

- подключить TTLock для генерации гостевого кода;
- отправлять email после webhook со ссылкой на Telegram-бота;
- добавить более точную защиту для показа кода замка;
- вынести контент по объектам в БД или админку.
