import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.access_code_service import AccessCodeService
from app.services.booking_service import BookingService
from app.services.telegram_service import TelegramService
from app.services.travelline_api_service import TravelLineApiError
from app.services.travelline_sync_service import TravelLineSyncService

router = APIRouter(prefix="/webhooks/travelline", tags=["travelline"])

logger = logging.getLogger(__name__)

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()
access_code_service = AccessCodeService()
travelline_sync_service = TravelLineSyncService()


def _check_webhook_secret(secret_header: str | None) -> None:
    if settings.travelline_webhook_secret and secret_header != settings.travelline_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid TravelLine secret")


def _check_sync_secret(secret_header: str | None) -> None:
    if settings.travelline_sync_secret and secret_header != settings.travelline_sync_secret:
        raise HTTPException(status_code=403, detail="Invalid TravelLine sync secret")


async def _handle_legacy_booking_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    payload_summary = booking_service.describe_payload(payload)
    logger.info(
        "travelline_legacy_webhook_received %s",
        json.dumps(payload_summary, ensure_ascii=False, sort_keys=True),
    )

    try:
        booking = booking_service.upsert_from_travelline(db, payload)
    except ValueError as exc:
        logger.warning(
            "travelline_legacy_webhook_ignored %s",
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
        "travelline_legacy_booking_upserted %s",
        json.dumps(booking_summary, ensure_ascii=False, sort_keys=True),
    )

    code_result = await access_code_service.try_prepare_code_for_booking(db, booking)
    code_summary = access_code_service.describe_prepare_result(booking, code_result)
    logger.info(
        "travelline_legacy_access_code_prepare_result %s",
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

    return {
        "ok": True,
        "mode": "legacy_payload",
        "booking_id": booking.id,
        "external_booking_id": booking.external_booking_id,
        "anomaly_flags": booking_service.get_anomaly_flags(payload, booking),
        "access_code_mode": access_code_service.access_code_mode,
    }


@router.post("")
async def travelline_webhook(
    payload: Any,
    db: Session = Depends(get_db),
    x_travelline_secret: str | None = Header(default=None),
):
    _check_webhook_secret(x_travelline_secret)

    if isinstance(payload, (list, dict)):
        events = travelline_sync_service.parse_event_batch(payload)
        if events:
            log_payload = {
                "events_count": len(events),
                "events": [event.to_log_dict() for event in events],
            }
            logger.info(
                "travelline_events_webhook_received %s",
                json.dumps(log_payload, ensure_ascii=False, sort_keys=True),
            )

            try:
                result = await travelline_sync_service.process_webhook_events(db, payload)
            except TravelLineApiError as exc:
                logger.exception("travelline_events_sync_failed")
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ValueError as exc:
                logger.warning("travelline_events_webhook_ignored %s", str(exc))
                return {"ok": True, "ignored": True, "reason": str(exc)}

            logger.info(
                "travelline_events_webhook_processed %s",
                json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
            )
            return {"ok": True, **result}

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Unsupported TravelLine payload format")

    return await _handle_legacy_booking_payload(db, payload)


@router.post("/sync/recent")
async def travelline_sync_recent(
    db: Session = Depends(get_db),
    x_travelline_sync_secret: str | None = Header(default=None),
):
    _check_sync_secret(x_travelline_sync_secret)

    try:
        result = await travelline_sync_service.sync_recent_bookings(db)
    except (TravelLineApiError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "travelline_manual_recent_sync %s",
        json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
    )
    return {"ok": True, **result}


@router.post("/sync/booking/{property_id}/{booking_number}")
async def travelline_sync_booking(
    property_id: str,
    booking_number: str,
    db: Session = Depends(get_db),
    x_travelline_sync_secret: str | None = Header(default=None),
):
    _check_sync_secret(x_travelline_sync_secret)

    try:
        result = await travelline_sync_service.sync_booking(db, property_id, booking_number)
    except (TravelLineApiError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "travelline_manual_booking_sync %s",
        json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
    )
    return {"ok": True, **result}
