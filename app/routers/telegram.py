from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.booking_service import BookingService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()


@router.post("/{secret}")
async def telegram_webhook(
    secret: str,
    update: dict,
    db: Session = Depends(get_db),
):
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid telegram webhook secret")

    message = update.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await telegram_service.send_message(
                chat_id,
                (
                    f"Ваша бронь найдена.\n"
                    f"Бронь: #{booking.external_booking_id}\n"
                    f"Статус: {booking.status or 'не указан'}\n"
                    f"Объект: {booking.property_name or 'не указан'}\n"
                    f"Номер: {booking.room_name or 'не указан'}"
                ),
            )
        else:
            await telegram_service.send_message(
                chat_id,
                "Привет. Пока бронь не привязана к вашему Telegram.\n"
                "Отправьте номер телефона в формате +79991234567.",
            )
        return {"ok": True}

    if text.startswith("+"):
        linked = booking_service.link_chat_to_guest_by_phone(db, chat_id, text)
        if linked:
            booking = booking_service.get_booking_by_chat_id(db, chat_id)
            if booking:
                await telegram_service.send_message(
                    chat_id,
                    (
                        f"Готово, бронь привязана.\n"
                        f"Бронь: #{booking.external_booking_id}\n"
                        f"Статус: {booking.status or 'не указан'}"
                    ),
                )
            else:
                await telegram_service.send_message(
                    chat_id,
                    "Телефон найден, но активная бронь пока не обнаружена."
                )
        else:
            await telegram_service.send_message(
                chat_id,
                "Бронь по этому телефону не найдена."
            )
        return {"ok": True}

    await telegram_service.send_message(
        chat_id,
        "Напишите /start или отправьте номер телефона в формате +79991234567."
    )
    return {"ok": True}
