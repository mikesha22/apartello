import json
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, Guest


PHONE_CLEAN_RE = re.compile(r"[^\d+]")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    cleaned = PHONE_CLEAN_RE.sub("", phone.strip())
    if not cleaned:
        return None
    if cleaned.startswith("8") and len(cleaned) == 11:
        return "+7" + cleaned[1:]
    if cleaned.startswith("7") and len(cleaned) == 11:
        return "+" + cleaned
    if cleaned.startswith("+"):
        return cleaned
    return cleaned


class BookingService:
    def upsert_from_travelline(self, db: Session, payload: dict) -> Booking:
        external_booking_id = str(
            payload.get("booking_id")
            or payload.get("reservation_id")
            or payload.get("id")
            or payload.get("booking", {}).get("id")
        )

        if not external_booking_id:
            raise ValueError("No booking id in payload")

        guest_payload = payload.get("guest", {})
        phone = normalize_phone(guest_payload.get("phone") or payload.get("phone"))
        email = guest_payload.get("email") or payload.get("email")
        full_name = (
            guest_payload.get("full_name")
            or guest_payload.get("name")
            or payload.get("customer_name")
        )

        guest = None
        if phone:
            guest = db.scalar(select(Guest).where(Guest.phone == phone))
            if guest is None:
                guest = Guest(phone=phone)
                db.add(guest)
                db.flush()

            if full_name:
                guest.full_name = full_name
            if email:
                guest.email = email

        booking = db.scalar(
            select(Booking).where(Booking.external_booking_id == external_booking_id)
        )

        if booking is None:
            booking = Booking(
                external_booking_id=external_booking_id,
                source="travelline",
            )
            db.add(booking)

        booking.guest = guest
        booking.status = payload.get("status") or payload.get("booking", {}).get("status")
        booking.property_name = (
            payload.get("property_name")
            or payload.get("hotel_name")
            or payload.get("property", {}).get("name")
        )
        booking.room_name = payload.get("room_name") or payload.get("room", {}).get("name")
        booking.checkin_at = parse_dt(payload.get("checkin_at") or payload.get("arrival_date"))
        booking.checkout_at = parse_dt(payload.get("checkout_at") or payload.get("departure_date"))
        booking.raw_payload = json.dumps(payload, ensure_ascii=False)

        db.commit()
        db.refresh(booking)
        return booking

    def get_booking_by_chat_id(self, db: Session, chat_id: int | str) -> Booking | None:
        guest = db.scalar(select(Guest).where(Guest.telegram_chat_id == str(chat_id)))
        if not guest:
            return None

        stmt = (
            select(Booking)
            .where(Booking.guest_id == guest.id)
            .order_by(Booking.created_at.desc())
        )
        return db.scalars(stmt).first()

    def find_latest_booking_by_phone(self, db: Session, phone: str) -> Booking | None:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            return None

        guest = db.scalar(select(Guest).where(Guest.phone == normalized_phone))
        if not guest:
            return None

        stmt = (
            select(Booking)
            .where(Booking.guest_id == guest.id)
            .order_by(Booking.created_at.desc())
        )
        return db.scalars(stmt).first()

    def link_chat_to_booking_guest(self, db: Session, chat_id: int | str, booking: Booking) -> None:
        if booking.guest is None:
            return
        booking.guest.telegram_chat_id = str(chat_id)
        db.commit()
