from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Booking
from app.services.access_code_service import AccessCodeService
from app.services.booking_service import BookingService, parse_dt
from app.services.telegram_service import TelegramService
from app.services.travelline_api_service import TravelLineApiService, TravelLineApiError
from app.services.travelline_models import (
    NormalizedBookingInput,
    TravelLineWebhookEvent,
)

logger = logging.getLogger(__name__)


class TravelLineSyncService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_service = TravelLineApiService()
        self.booking_service = BookingService()
        self.access_code_service = AccessCodeService()
        self.telegram_service = TelegramService()

    def resolve_property_ids(self, explicit_property_ids: list[str] | None = None) -> list[str]:
        values = explicit_property_ids or self.settings.parsed_travelline_property_ids()
        if not values:
            raise ValueError(
                "No TravelLine property ids configured. "
                "Set TRAVELLINE_PROPERTY_IDS or pass property ids explicitly."
            )
        return values

    def is_api_configured(self) -> bool:
        return self.api_service.is_configured()

    def _fallback_property_name(self, property_id: str) -> str:
        return f"TravelLine property {property_id}"

    def _extract_room_name(self, booking_data: dict[str, Any]) -> str | None:
        room_stays = booking_data.get("roomStays") or []
        if not room_stays:
            return None

        room_stay = room_stays[0] if isinstance(room_stays[0], dict) else {}
        room_type = room_stay.get("roomType") if isinstance(room_stay.get("roomType"), dict) else {}
        room = room_stay.get("room") if isinstance(room_stay.get("room"), dict) else {}

        for candidate in (
            room.get("displayName"),
            room.get("name"),
            room_type.get("name"),
        ):
            if candidate:
                return str(candidate)
        return None

    def _extract_dates(self, booking_data: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
        room_stays = booking_data.get("roomStays") or []
        if not room_stays:
            return None, None

        room_stay = room_stays[0] if isinstance(room_stays[0], dict) else {}
        stay_dates = room_stay.get("stayDates") if isinstance(room_stay.get("stayDates"), dict) else {}
        checkin_at = parse_dt(stay_dates.get("arrivalDateTime"))
        checkout_at = parse_dt(stay_dates.get("departureDateTime"))
        return checkin_at, checkout_at

    def _extract_guest_name(self, booking_data: dict[str, Any]) -> str | None:
        customer = booking_data.get("customer")
        if isinstance(customer, dict):
            for key in ("fullName", "name", "displayName"):
                value = customer.get(key)
                if value:
                    return str(value)

        room_stays = booking_data.get("roomStays") or []
        if room_stays and isinstance(room_stays[0], dict):
            guests = room_stays[0].get("guests") or []
            if guests and isinstance(guests[0], dict):
                for key in ("fullName", "name", "displayName"):
                    value = guests[0].get(key)
                    if value:
                        return str(value)

        return None

    def normalize_booking_details(
        self,
        property_id: str,
        raw_details: dict[str, Any],
    ) -> NormalizedBookingInput:
        booking_data = raw_details.get("booking") if isinstance(raw_details.get("booking"), dict) else raw_details
        if not isinstance(booking_data, dict):
            raise ValueError("TravelLine booking details response has no booking object")

        number = booking_data.get("number")
        if not number:
            raise ValueError("TravelLine booking details response has no booking number")

        checkin_at, checkout_at = self._extract_dates(booking_data)

        return NormalizedBookingInput(
            external_booking_id=str(number),
            source="travelline_api",
            status=str(booking_data.get("status")) if booking_data.get("status") is not None else None,
            property_name=self._fallback_property_name(property_id),
            room_name=self._extract_room_name(booking_data),
            checkin_at=checkin_at,
            checkout_at=checkout_at,
            guest_name=self._extract_guest_name(booking_data),
            guest_phone=None,
            guest_email=None,
            raw_payload=raw_details,
        )

    async def _post_upsert_actions(self, db: Session, booking: Booking) -> dict[str, Any]:
        code_result = await self.access_code_service.try_prepare_code_for_booking(db, booking)
        code_summary = self.access_code_service.describe_prepare_result(booking, code_result)

        telegram_sent = False
        if booking.guest and booking.guest.telegram_chat_id:
            text = (
                f"Обновление по бронированию #{booking.external_booking_id}\n"
                f"Статус: {booking.status or 'не указан'}\n"
                f"Объект: {booking.property_name or 'не указан'}\n"
                f"Номер: {booking.room_name or 'не указан'}"
            )
            await self.telegram_service.send_message(booking.guest.telegram_chat_id, text)
            telegram_sent = True

        return {
            "booking": self.booking_service.describe_booking(booking),
            "access_code": code_summary,
            "telegram_sent": telegram_sent,
        }

    async def sync_booking(self, db: Session, property_id: str, booking_number: str) -> dict[str, Any]:
        details = await self.api_service.get_booking_details(property_id, booking_number)
        normalized = self.normalize_booking_details(property_id, details)
        booking = self.booking_service.upsert_from_normalized(db, normalized)
        post_actions = await self._post_upsert_actions(db, booking)
        return {
            "property_id": property_id,
            "booking_number": booking_number,
            **post_actions,
        }

    async def sync_recent_bookings(
        self,
        db: Session,
        *,
        property_ids: list[str] | None = None,
        last_modification: str | None = None,
        count: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        property_ids = self.resolve_property_ids(property_ids)
        count = count or self.settings.travelline_sync_page_size
        max_pages = max_pages or self.settings.travelline_sync_max_pages

        if last_modification is None:
            lookback = timedelta(minutes=self.settings.travelline_sync_lookback_minutes)
            last_modification = (datetime.utcnow() - lookback).strftime("%Y-%m-%dT%H:%M:%SZ")

        result: dict[str, Any] = {
            "mode": "api_recent_sync",
            "property_ids": property_ids,
            "last_modification": last_modification,
            "properties": [],
            "synced_bookings": 0,
            "errors": [],
        }

        for property_id in property_ids:
            property_result = {
                "property_id": property_id,
                "pages": 0,
                "booking_numbers": [],
            }
            continue_token: str | None = None

            for page_index in range(max_pages):
                page = await self.api_service.list_booking_summaries(
                    property_id,
                    continue_token=continue_token,
                    last_modification=last_modification if continue_token is None else None,
                    count=count,
                )
                property_result["pages"] += 1

                summaries = page.get("bookingSummaries") or []
                for summary in summaries:
                    booking_number = summary.get("number")
                    if not booking_number:
                        continue
                    try:
                        sync_result = await self.sync_booking(db, property_id, str(booking_number))
                        property_result["booking_numbers"].append(sync_result["booking_number"])
                        result["synced_bookings"] += 1
                    except Exception as exc:  # noqa: BLE001
                        error_text = f"{property_id}:{booking_number}: {exc}"
                        result["errors"].append(error_text)
                        logger.exception("travelline_sync_booking_failed %s", error_text)

                continue_token = page.get("continueToken")
                has_more_data = bool(page.get("hasMoreData"))
                if not has_more_data or not continue_token:
                    break

            result["properties"].append(property_result)

        return result

    def parse_event_batch(self, payload: Any) -> list[TravelLineWebhookEvent]:
        raw_events: list[dict[str, Any]] = []

        if isinstance(payload, list):
            raw_events = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            if isinstance(payload.get("events"), list):
                raw_events = [item for item in payload["events"] if isinstance(item, dict)]
            elif payload.get("eventType") or payload.get("event_type"):
                raw_events = [payload]

        return [TravelLineWebhookEvent.from_any(item) for item in raw_events]

    async def process_webhook_events(self, db: Session, payload: Any) -> dict[str, Any]:
        events = self.parse_event_batch(payload)
        if not events:
            raise ValueError("No TravelLine events found in webhook payload")

        result: dict[str, Any] = {
            "mode": "webhook_events",
            "events_count": len(events),
            "events": [event.to_log_dict() for event in events],
            "synced": [],
            "fallback_sync": None,
        }

        handled_pairs: set[tuple[str, str]] = set()
        property_ids_to_refresh: set[str] = set()

        for event in events:
            property_id = event.extract_property_id()
            booking_number = event.extract_booking_number()

            if property_id and booking_number:
                pair = (property_id, booking_number)
                if pair in handled_pairs:
                    continue
                handled_pairs.add(pair)
                try:
                    sync_result = await self.sync_booking(db, property_id, booking_number)
                    result["synced"].append(sync_result)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "travelline_webhook_sync_booking_failed property_id=%s booking_number=%s",
                        property_id,
                        booking_number,
                    )
                    result.setdefault("errors", []).append(
                        f"{property_id}:{booking_number}: {exc}"
                    )
                continue

            if property_id:
                property_ids_to_refresh.add(property_id)

        if property_ids_to_refresh:
            try:
                result["fallback_sync"] = await self.sync_recent_bookings(
                    db,
                    property_ids=sorted(property_ids_to_refresh),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("travelline_webhook_fallback_sync_failed")
                result.setdefault("errors", []).append(f"fallback_sync: {exc}")

        return result
