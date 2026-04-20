import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, Guest
from app.services.travelline_models import NormalizedBookingInput

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


def _first_present(*values: Any) -> Any | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        return value
    return None


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


class BookingService:
    def extract_external_booking_id(self, payload: dict) -> str | None:
        booking_payload = _as_dict(payload.get("booking"))
        value = _first_present(
            payload.get("booking_id"),
            payload.get("reservation_id"),
            payload.get("number"),
            payload.get("id"),
            booking_payload.get("number"),
            booking_payload.get("id"),
        )
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def extract_status(self, payload: dict) -> str | None:
        booking_payload = _as_dict(payload.get("booking"))
        value = _first_present(payload.get("status"), booking_payload.get("status"))
        return str(value) if value is not None else None

    def extract_property_name(self, payload: dict) -> str | None:
        property_payload = _as_dict(payload.get("property"))
        value = _first_present(
            payload.get("property_name"),
            payload.get("hotel_name"),
            property_payload.get("name"),
        )
        return str(value) if value is not None else None

    def extract_room_name(self, payload: dict) -> str | None:
        room_payload = _as_dict(payload.get("room"))
        value = _first_present(payload.get("room_name"), room_payload.get("name"))
        return str(value) if value is not None else None

    def extract_guest_payload(self, payload: dict) -> dict:
        return _as_dict(payload.get("guest"))

    def extract_guest_phone(self, payload: dict) -> str | None:
        guest_payload = self.extract_guest_payload(payload)
        return normalize_phone(
            _first_present(
                guest_payload.get("phone"),
                payload.get("phone"),
            )
        )

    def extract_guest_email(self, payload: dict) -> str | None:
        guest_payload = self.extract_guest_payload(payload)
        value = _first_present(guest_payload.get("email"), payload.get("email"))
        return str(value) if value is not None else None

    def extract_guest_name(self, payload: dict) -> str | None:
        guest_payload = self.extract_guest_payload(payload)
        value = _first_present(
            guest_payload.get("full_name"),
            guest_payload.get("name"),
            payload.get("customer_name"),
        )
        return str(value) if value is not None else None

    def normalize_legacy_travelline_payload(self, payload: dict) -> NormalizedBookingInput:
        external_booking_id = self.extract_external_booking_id(payload)
        if not external_booking_id:
            raise ValueError("Missing booking id in payload")

        return NormalizedBookingInput(
            external_booking_id=external_booking_id,
            source="travelline",
            status=self.extract_status(payload),
            property_name=self.extract_property_name(payload),
            room_name=self.extract_room_name(payload),
            checkin_at=parse_dt(payload.get("checkin_at") or payload.get("arrival_date")),
            checkout_at=parse_dt(payload.get("checkout_at") or payload.get("departure_date")),
            guest_name=self.extract_guest_name(payload),
            guest_phone=self.extract_guest_phone(payload),
            guest_email=self.extract_guest_email(payload),
            raw_payload=payload,
        )

    def get_anomaly_flags(self, payload: dict, booking: Booking | None = None) -> list[str]:
        flags: list[str] = []

        external_booking_id = booking.external_booking_id if booking else self.extract_external_booking_id(payload)
        phone = booking.guest.phone if booking and booking.guest else self.extract_guest_phone(payload)
        property_name = booking.property_name if booking else self.extract_property_name(payload)
        room_name = booking.room_name if booking else self.extract_room_name(payload)
        checkin_at = booking.checkin_at if booking else parse_dt(payload.get("checkin_at") or payload.get("arrival_date"))
        checkout_at = booking.checkout_at if booking else parse_dt(payload.get("checkout_at") or payload.get("departure_date"))

        if not external_booking_id:
            flags.append("missing_booking_id")
        if not phone:
            flags.append("missing_phone")
        if not property_name:
            flags.append("missing_property_name")
        if not room_name:
            flags.append("missing_room_name")
        if checkin_at is None:
            flags.append("missing_checkin_at")
        if checkout_at is None:
            flags.append("missing_checkout_at")

        if checkin_at and checkout_at and checkout_at <= checkin_at:
            flags.append("invalid_booking_window")

        return flags

    def describe_payload(self, payload: dict) -> dict[str, Any]:
        guest_payload = self.extract_guest_payload(payload)
        return {
            "external_booking_id": self.extract_external_booking_id(payload),
            "status": self.extract_status(payload),
            "property_name": self.extract_property_name(payload),
            "room_name": self.extract_room_name(payload),
            "normalized_phone": self.extract_guest_phone(payload),
            "guest_email": self.extract_guest_email(payload),
            "guest_name": self.extract_guest_name(payload),
            "has_guest_object": bool(guest_payload),
            "payload_keys": sorted(payload.keys()),
            "anomaly_flags": self.get_anomaly_flags(payload),
        }

    def describe_booking(self, booking: Booking) -> dict[str, Any]:
        return {
            "booking_id": booking.id,
            "external_booking_id": booking.external_booking_id,
            "status": booking.status,
            "property_name": booking.property_name,
            "room_name": booking.room_name,
            "guest_id": booking.guest_id,
            "normalized_phone": booking.guest.phone if booking.guest else None,
            "guest_email": booking.guest.email if booking.guest else None,
            "checkin_at": booking.checkin_at.isoformat() if booking.checkin_at else None,
            "checkout_at": booking.checkout_at.isoformat() if booking.checkout_at else None,
        }

    def upsert_from_travelline(self, db: Session, payload: dict) -> Booking:
        normalized = self.normalize_legacy_travelline_payload(payload)
        return self.upsert_from_normalized(db, normalized)

    def upsert_from_normalized(self, db: Session, data: NormalizedBookingInput) -> Booking:
        guest = None
        if data.guest_phone:
            guest = db.scalar(select(Guest).where(Guest.phone == data.guest_phone))
            if guest is None:
                guest = Guest(phone=data.guest_phone)
                db.add(guest)
                db.flush()

            if data.guest_name:
                guest.full_name = data.guest_name
            if data.guest_email:
                guest.email = data.guest_email
        elif data.guest_email:
            existing_guest = db.scalar(select(Guest).where(Guest.email == data.guest_email))
            if existing_guest is not None:
                guest = existing_guest
                if data.guest_name:
                    guest.full_name = data.guest_name

        booking = db.scalar(select(Booking).where(Booking.external_booking_id == data.external_booking_id))
        if booking is None:
            booking = Booking(
                external_booking_id=data.external_booking_id,
                source=data.source or "travelline",
            )
            db.add(booking)

        if guest is not None:
            booking.guest = guest

        booking.source = data.source or booking.source or "travelline"
        booking.status = data.status
        booking.property_name = data.property_name
        booking.room_name = data.room_name
        booking.checkin_at = data.checkin_at
        booking.checkout_at = data.checkout_at
        booking.raw_payload = json.dumps(data.raw_payload, ensure_ascii=False) if data.raw_payload is not None else None

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
