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
                [{"text": "Моя бронь"}, {"text": "Как заселиться"}],
                [{"text": "Маршрут"}, {"text": "Поддержка"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }