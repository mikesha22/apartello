import httpx

from app.config import get_settings

settings = get_settings()


class TelegramService:
    def __init__(self) -> None:
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/editMessageText",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> dict:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def set_webhook(self, public_base_url: str) -> dict:
        webhook_url = f"{public_base_url}/webhooks/telegram/{settings.telegram_webhook_secret}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/setWebhook",
                json={"url": webhook_url},
            )
            response.raise_for_status()
            return response.json()

    def main_menu(self) -> dict:
        return {
            "keyboard": [
                [{"text": "Моя бронь"}, {"text": "Заселение"}],
                [{"text": "Проживание"}, {"text": "Поддержка"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }

    def contact_request_menu(self) -> dict:
        return {
            "keyboard": [
                [{"text": "Поделиться моим номером", "request_contact": True}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def booking_menu(self) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "Обновить", "callback_data": "booking_refresh"}],
                [
                    {"text": "Показать детали", "callback_data": "booking_details"},
                    {"text": "Показать даты", "callback_data": "booking_dates"},
                ],
                [{"text": "Назад", "callback_data": "back_main"}],
            ]
        }

    def checkin_menu(self) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "Показать код доступа", "callback_data": "checkin_code"}],
                [
                    {"text": "Как добраться", "callback_data": "checkin_route"},
                    {"text": "Инструкция по входу", "callback_data": "checkin_instruction"},
                ],
                [
                    {"text": "Фото входа", "callback_data": "checkin_photo"},
                    {"text": "Адрес", "callback_data": "checkin_address"},
                ],
                [{"text": "Назад", "callback_data": "back_main"}],
            ]
        }

    def stay_menu(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "Wi‑Fi", "callback_data": "stay_wifi"},
                    {"text": "Правила проживания", "callback_data": "stay_rules"},
                ],
                [{"text": "Сообщить о проблеме", "callback_data": "stay_problem"}],
                [{"text": "Продлить проживание", "callback_data": "stay_extend"}],
                [{"text": "Назад", "callback_data": "back_main"}],
            ]
        }

    def support_menu(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "Позвонить", "callback_data": "support_call"},
                    {"text": "Написать в Telegram", "callback_data": "support_telegram"},
                ],
                [
                    {"text": "WhatsApp", "callback_data": "support_whatsapp"},
                    {"text": "Срочная помощь", "callback_data": "support_urgent"},
                ],
                [{"text": "Назад", "callback_data": "back_main"}],
            ]
        }

    def problem_menu(self) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "Не могу войти", "callback_data": "problem_cant_enter"}],
                [{"text": "Не работает код", "callback_data": "problem_code"}],
                [{"text": "Нет Wi‑Fi", "callback_data": "problem_wifi"}],
                [{"text": "Проблема в апартаменте", "callback_data": "problem_room"}],
                [{"text": "Связаться с поддержкой", "callback_data": "problem_support"}],
                [{"text": "Назад", "callback_data": "back_stay"}],
            ]
        }
