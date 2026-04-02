import httpx

from app.config import get_settings

settings = get_settings()


class TelegramService:
    def __init__(self) -> None:
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    async def send_message(self, chat_id: int | str, text: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                },
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
