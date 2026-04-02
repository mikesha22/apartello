from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
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
