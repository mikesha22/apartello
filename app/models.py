from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="guest")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("external_booking_id", name="uq_booking_external_booking_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_booking_id: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(50), default="travelline")

    guest_id: Mapped[int | None] = mapped_column(ForeignKey("guests.id"), nullable=True)
    guest: Mapped[Guest | None] = relationship(back_populates="bookings")

    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    room_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    email_verifications: Mapped[list["EmailVerification"]] = relationship(back_populates="booking")
    access_codes: Mapped[list["BookingAccessCode"]] = relationship(back_populates="booking")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    chat_id: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))

    attempts_left: Mapped[int] = mapped_column(Integer, default=5)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime)
    resend_available_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship(back_populates="email_verifications")


class LockBinding(Base):
    __tablename__ = "lock_bindings"
    __table_args__ = (
        UniqueConstraint("property_name", "room_name", name="uq_lock_binding_property_room"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    property_name: Mapped[str] = mapped_column(String(255), index=True)
    room_name: Mapped[str] = mapped_column(String(255), index=True)
    lock_id: Mapped[int] = mapped_column(Integer, index=True)
    keyboard_pwd_version: Mapped[int] = mapped_column(Integer)
    lock_alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    access_codes: Mapped[list["BookingAccessCode"]] = relationship(back_populates="lock_binding")


class BookingAccessCode(Base):
    __tablename__ = "booking_access_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    lock_binding_id: Mapped[int] = mapped_column(ForeignKey("lock_bindings.id"), index=True)
    source: Mapped[str] = mapped_column(String(50), default="ttlock")
    status: Mapped[str] = mapped_column(String(50), default="generated", index=True)

    keyboard_pwd: Mapped[str | None] = mapped_column(String(64), nullable=True)
    keyboard_pwd_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime] = mapped_column(DateTime)
    reveal_from: Mapped[datetime] = mapped_column(DateTime)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    booking: Mapped[Booking] = relationship(back_populates="access_codes")
    lock_binding: Mapped[LockBinding] = relationship(back_populates="access_codes")
