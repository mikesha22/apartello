import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, Guest


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


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

        phone = payload.get("guest", {}).get("phone") or payload.get("phone")
        full_name = (
            payload.get("guest", {}).get("full_name")
            or payload.get("guest", {}).get("name")
            or payload.get("customer_name")
        )

        guest = None
        if phone:
            guest = db.scalar(select(Guest).where(Guest.phone == phone))
            if guest is None:
                guest = Guest(phone=phone, full_name=full_name)
                db.add(guest)
                db.flush()

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

    def link_chat_to_guest_by_phone(self, db: Session, chat_id: int | str, phone: str) -> bool:
        guest = db.scalar(select(Guest).where(Guest.phone == phone))
        if not guest:
            return False

        guest.telegram_chat_id = str(chat_id)
        db.commit()
        return True
