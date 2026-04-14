import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.access_code_service import AccessCodeService
from app.services.booking_service import BookingService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/travelline", tags=["travelline"])

logger = logging.getLogger(__name__)

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
    payload_summary = booking_service.describe_payload(payload)
    logger.info(
        "travelline_webhook_received %s",
        json.dumps(payload_summary, ensure_ascii=False, sort_keys=True),
    )

    if settings.travelline_webhook_secret:
        if x_travelline_secret != settings.travelline_webhook_secret:
            logger.warning(
                "travelline_webhook_rejected_invalid_secret %s",
                json.dumps(payload_summary, ensure_ascii=False, sort_keys=True),
            )
            raise HTTPException(status_code=403, detail="Invalid TravelLine secret")

    try:
        booking = booking_service.upsert_from_travelline(db, payload)
    except ValueError as exc:
        logger.warning(
            "travelline_webhook_ignored %s",
            json.dumps(
                {
                    **payload_summary,
                    "ignored": True,
                    "reason": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return {
            "ok": True,
            "ignored": True,
            "reason": str(exc),
            "payload_summary": payload_summary,
        }

    booking_summary = booking_service.describe_booking(booking)
    logger.info(
        "travelline_booking_upserted %s",
        json.dumps(booking_summary, ensure_ascii=False, sort_keys=True),
    )

    code_result = await access_code_service.try_prepare_code_for_booking(db, booking)
    code_summary = access_code_service.describe_prepare_result(booking, code_result)
    logger.info(
        "travelline_access_code_prepare_result %s",
        json.dumps(code_summary, ensure_ascii=False, sort_keys=True),
    )

    if booking.guest and booking.guest.telegram_chat_id:
        text = (
            f"Обновление по бронированию #{booking.external_booking_id}\n"
            f"Статус: {booking.status or 'не указан'}\n"
            f"Объект: {booking.property_name or 'не указан'}\n"
            f"Номер: {booking.room_name or 'не указан'}"
        )
        await telegram_service.send_message(booking.guest.telegram_chat_id, text)
        logger.info(
            "travelline_telegram_notification_sent %s",
            json.dumps(
                {
                    "booking_id": booking.id,
                    "external_booking_id": booking.external_booking_id,
                    "chat_id": booking.guest.telegram_chat_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    else:
        logger.info(
            "travelline_telegram_notification_skipped %s",
            json.dumps(
                {
                    "booking_id": booking.id,
                    "external_booking_id": booking.external_booking_id,
                    "reason": "guest_chat_not_linked",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    return {
        "ok": True,
        "booking_id": booking.id,
        "external_booking_id": booking.external_booking_id,
        "anomaly_flags": booking_service.get_anomaly_flags(payload, booking),
        "access_code_mode": access_code_service.access_code_mode,
    }
