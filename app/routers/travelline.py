from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.access_code_service import AccessCodeService
from app.services.booking_service import BookingService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/travelline", tags=["travelline"])

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()
access_code_service = AccessCodeService()


@router.post("")
async def travelline_webhook(
    payload: dict,
    db: Session = Depends(get_db),
    x_travelline_secret: str | None = Header(default=None),
):
    if settings.travelline_webhook_secret:
        if x_travelline_secret != settings.travelline_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid TravelLine secret")

    booking = booking_service.upsert_from_travelline(db, payload)
    await access_code_service.try_prepare_code_for_booking(db, booking)

    if booking.guest and booking.guest.telegram_chat_id:
        text = (
            f"Обновление по бронированию #{booking.external_booking_id}\n"
            f"Статус: {booking.status or 'не указан'}\n"
            f"Объект: {booking.property_name or 'не указан'}\n"
            f"Номер: {booking.room_name or 'не указан'}"
        )
        await telegram_service.send_message(booking.guest.telegram_chat_id, text)

    return {
        "ok": True,
        "booking_id": booking.id,
        "external_booking_id": booking.external_booking_id,
    }
