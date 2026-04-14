from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Booking, BookingAccessCode, LockBinding
from app.services.ttlock_mapping_service import TTLockMappingService
from app.services.ttlock_service import TTLockService


@dataclass(slots=True)
class AccessCodeMessage:
    text: str
    code: BookingAccessCode | None = None


class AccessCodeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.access_code_mode = (self.settings.access_code_mode or "ttlock").strip().lower()
        self.ttlock_service = TTLockService()
        self.mapping_service = TTLockMappingService()
        self.reveal_offset = timedelta(minutes=15)

    def _normalize_booking_times(self, booking: Booking) -> tuple[datetime, datetime]:
        if booking.checkin_at is None or booking.checkout_at is None:
            raise ValueError("Booking has no check-in/check-out dates")
        return booking.checkin_at, booking.checkout_at

    def _default_reveal_from(self, booking: Booking) -> datetime:
        checkin_at, _ = self._normalize_booking_times(booking)
        return checkin_at - self.reveal_offset

    def _active_statuses(self) -> tuple[str, ...]:
        return ("generated", "revealed")

    def _test_code_from_phone(self, booking: Booking) -> str | None:
        if booking.guest is None or not booking.guest.phone:
            return None

        digits = "".join(ch for ch in booking.guest.phone if ch.isdigit())
        if len(digits) < 4:
            return None

        return digits[-4:]

    def get_binding_for_booking(self, db: Session, booking: Booking) -> LockBinding | None:
        return self.mapping_service.get_lock_binding(db, booking.property_name, booking.room_name)

    def get_latest_code(self, db: Session, booking_id: int) -> BookingAccessCode | None:
        stmt = (
            select(BookingAccessCode)
            .where(BookingAccessCode.booking_id == booking_id)
            .order_by(desc(BookingAccessCode.created_at), desc(BookingAccessCode.id))
        )
        return db.scalars(stmt).first()

    def get_current_code(self, db: Session, booking: Booking) -> BookingAccessCode | None:
        stmt = (
            select(BookingAccessCode)
            .where(
                BookingAccessCode.booking_id == booking.id,
                BookingAccessCode.status.in_(self._active_statuses()),
            )
            .order_by(desc(BookingAccessCode.created_at), desc(BookingAccessCode.id))
        )
        return db.scalars(stmt).first()

    def _matches_booking_window(self, code: BookingAccessCode, booking: Booking, binding: LockBinding) -> bool:
        checkin_at, checkout_at = self._normalize_booking_times(booking)
        return (
            code.lock_binding_id == binding.id
            and code.valid_from == checkin_at
            and code.valid_to == checkout_at
            and code.status in self._active_statuses()
            and code.keyboard_pwd is not None
        )

    def expire_outdated_codes(self, db: Session, booking: Booking) -> None:
        now = datetime.utcnow()
        stmt = select(BookingAccessCode).where(
            BookingAccessCode.booking_id == booking.id,
            BookingAccessCode.status.in_(self._active_statuses()),
            BookingAccessCode.valid_to < now,
        )
        items = db.scalars(stmt).all()
        changed = False
        for item in items:
            item.status = "expired"
            changed = True
        if changed:
            db.commit()

    async def ensure_code_for_booking(self, db: Session, booking: Booking) -> BookingAccessCode:
        binding = self.get_binding_for_booking(db, booking)
        if binding is None:
            raise ValueError(
                "No lock binding found for this booking. "
                "Add a record to lock_bindings first."
            )

        current = self.get_current_code(db, booking)
        if current is not None and self._matches_booking_window(current, booking, binding):
            return current

        if current is not None and current.status in self._active_statuses():
            current.status = "cancelled"
            current.revoked_at = datetime.utcnow()
            db.commit()

        checkin_at, checkout_at = self._normalize_booking_times(booking)
        reveal_from = self._default_reveal_from(booking)
        result = await self.ttlock_service.generate_period_code(
            lock_id=binding.lock_id,
            keyboard_pwd_version=binding.keyboard_pwd_version,
            start_at=checkin_at,
            end_at=checkout_at,
            keyboard_pwd_name=f"Guest {booking.external_booking_id}",
        )

        access_code = BookingAccessCode(
            booking_id=booking.id,
            lock_binding_id=binding.id,
            source="ttlock",
            status="generated",
            keyboard_pwd=result.get("keyboard_pwd"),
            keyboard_pwd_id=(
                str(result.get("keyboard_pwd_id"))
                if result.get("keyboard_pwd_id") is not None
                else None
            ),
            valid_from=checkin_at,
            valid_to=checkout_at,
            reveal_from=reveal_from,
            last_error=None,
        )
        db.add(access_code)
        db.commit()
        db.refresh(access_code)
        return access_code

    async def try_prepare_code_for_booking(self, db: Session, booking: Booking) -> BookingAccessCode | None:
        if booking.status and booking.status.lower() in {"cancelled", "canceled"}:
            self.cancel_codes_for_booking(db, booking, reason="Booking cancelled")
            return None

        if self.access_code_mode == "phone_last4":
            return None

        if booking.checkin_at is None or booking.checkout_at is None:
            return None

        binding = self.get_binding_for_booking(db, booking)
        if binding is None:
            return None

        current = self.get_current_code(db, booking)
        if current is not None and self._matches_booking_window(current, booking, binding):
            return current

        try:
            return await self.ensure_code_for_booking(db, booking)
        except Exception as exc:
            self.save_generation_error(db, booking, binding, str(exc))
            return None

    def save_generation_error(
        self,
        db: Session,
        booking: Booking,
        binding: LockBinding,
        error_text: str,
    ) -> BookingAccessCode:
        latest = self.get_latest_code(db, booking.id)
        if latest is not None and latest.status == "failed" and latest.lock_binding_id == binding.id:
            latest.last_error = error_text
            db.commit()
            db.refresh(latest)
            return latest

        checkin_at, checkout_at = self._normalize_booking_times(booking)
        failed = BookingAccessCode(
            booking_id=booking.id,
            lock_binding_id=binding.id,
            source="ttlock",
            status="failed",
            valid_from=checkin_at,
            valid_to=checkout_at,
            reveal_from=self._default_reveal_from(booking),
            last_error=error_text,
        )
        db.add(failed)
        db.commit()
        db.refresh(failed)
        return failed

    def cancel_codes_for_booking(self, db: Session, booking: Booking, reason: str | None = None) -> None:
        stmt = select(BookingAccessCode).where(
            BookingAccessCode.booking_id == booking.id,
            BookingAccessCode.status.in_(("generated", "revealed", "failed")),
        )
        items = db.scalars(stmt).all()
        changed = False
        for item in items:
            item.status = "cancelled"
            item.revoked_at = datetime.utcnow()
            if reason:
                item.last_error = reason
            changed = True
        if changed:
            db.commit()

    def _get_phone_last4_message(
        self,
        booking: Booking,
        now: datetime,
    ) -> AccessCodeMessage:
        if booking.status and booking.status.lower() in {"cancelled", "canceled"}:
            return AccessCodeMessage(
                "Бронирование отменено. Если это ошибка, обратитесь в поддержку."
            )

        code_value = self._test_code_from_phone(booking)
        if code_value is None:
            return AccessCodeMessage(
                "Тестовый код доступа пока недоступен. "
                "Не удалось определить номер телефона гостя."
            )

        if booking.checkin_at and now < (booking.checkin_at - self.reveal_offset):
            return AccessCodeMessage(
                "Код доступа пока недоступен. "
                "Он появится ближе ко времени заселения."
            )

        valid_from = booking.checkin_at.strftime("%d.%m.%Y %H:%M") if booking.checkin_at else "не указано"
        valid_to = booking.checkout_at.strftime("%d.%m.%Y %H:%M") if booking.checkout_at else "не указано"
        lock_name = booking.room_name or "вашего апартамента"

        return AccessCodeMessage(
            (
                f"Тестовый код доступа для {lock_name}:\n\n"
                f"{code_value}\n\n"
                f"Действует с {valid_from} до {valid_to}.\n"
                "Сейчас это временный тестовый режим по последним 4 цифрам телефона гостя."
            )
        )

    def get_code_message(self, db: Session, booking: Booking, now: datetime | None = None) -> AccessCodeMessage:
        now = now or datetime.utcnow()

        if self.access_code_mode == "phone_last4":
            return self._get_phone_last4_message(booking, now)

        self.expire_outdated_codes(db, booking)
        code = self.get_current_code(db, booking)
        if code is None:
            failed = self.get_latest_code(db, booking.id)
            if failed is not None and failed.status == "failed":
                return AccessCodeMessage(
                    "Не удалось подготовить код доступа автоматически.\n"
                    "Пожалуйста, обратитесь в поддержку.",
                    failed,
                )
            return AccessCodeMessage(
                "Код доступа пока не подготовлен. Если заезд уже начался, обратитесь в поддержку."
            )

        if now < code.reveal_from:
            return AccessCodeMessage(
                "Код доступа пока недоступен.\n"
                "Он появится ближе ко времени заселения."
            )

        if code.delivered_at is None:
            code.delivered_at = now
            code.status = "revealed"
            db.commit()
            db.refresh(code)

        lock_name = code.lock_binding.lock_alias or booking.room_name or "вашего апартамента"
        return AccessCodeMessage(
            (
                f"Код доступа для {lock_name}:\n\n"
                f"{code.keyboard_pwd}\n\n"
                f"Действует с {code.valid_from.strftime('%d.%m.%Y %H:%M')} "
                f"до {code.valid_to.strftime('%d.%m.%Y %H:%M')}.\n"
                "Не передавайте код третьим лицам."
            ),
            code,
        )

    def describe_prepare_result(self, booking: Booking, code: BookingAccessCode | None) -> dict:
        if booking.status and booking.status.lower() in {"cancelled", "canceled"}:
            return {
                "booking_id": booking.id,
                "external_booking_id": booking.external_booking_id,
                "mode": self.access_code_mode,
                "prepared": False,
                "reason": "booking_cancelled",
            }

        if self.access_code_mode == "phone_last4":
            test_code = self._test_code_from_phone(booking)
            return {
                "booking_id": booking.id,
                "external_booking_id": booking.external_booking_id,
                "mode": self.access_code_mode,
                "prepared": bool(test_code),
                "reason": "phone_last4_ready" if test_code else "missing_guest_phone",
                "test_code_preview": test_code,
            }

        return {
            "booking_id": booking.id,
            "external_booking_id": booking.external_booking_id,
            "mode": self.access_code_mode,
            "prepared": code is not None,
            "reason": code.status if code is not None else "not_prepared",
            "keyboard_pwd_id": code.keyboard_pwd_id if code is not None else None,
        }
