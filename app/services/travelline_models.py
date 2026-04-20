from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class NormalizedBookingInput:
    external_booking_id: str
    source: str = "travelline"
    status: str | None = None
    property_name: str | None = None
    room_name: str | None = None
    checkin_at: Any | None = None
    checkout_at: Any | None = None
    guest_name: str | None = None
    guest_phone: str | None = None
    guest_email: str | None = None
    raw_payload: dict | list | str | None = None


@dataclass(slots=True)
class TravelLineWebhookEvent:
    event_type: str
    creation_time: str | None
    payload_raw: str | dict | None
    payload_data: dict[str, Any]

    @classmethod
    def from_any(cls, value: dict[str, Any]) -> "TravelLineWebhookEvent":
        payload_raw = value.get("payload")
        payload_data: dict[str, Any] = {}

        if isinstance(payload_raw, dict):
            payload_data = payload_raw
        elif isinstance(payload_raw, str) and payload_raw.strip():
            try:
                decoded = json.loads(payload_raw)
                if isinstance(decoded, dict):
                    payload_data = decoded
            except json.JSONDecodeError:
                payload_data = {}

        return cls(
            event_type=str(value.get("eventType") or value.get("event_type") or "unknown"),
            creation_time=value.get("creationTime") or value.get("creation_time"),
            payload_raw=payload_raw,
            payload_data=payload_data,
        )

    def extract_property_id(self) -> str | None:
        candidates = (
            self.payload_data.get("propertyId"),
            self.payload_data.get("property_id"),
            self.payload_data.get("hotelId"),
            self.payload_data.get("hotel_id"),
        )
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def extract_booking_number(self) -> str | None:
        candidates = (
            self.payload_data.get("number"),
            self.payload_data.get("bookingNumber"),
            self.payload_data.get("booking_number"),
            self.payload_data.get("reservationNumber"),
            self.payload_data.get("reservation_number"),
            self.payload_data.get("bookingId"),
            self.payload_data.get("booking_id"),
            self.payload_data.get("reservationId"),
            self.payload_data.get("reservation_id"),
            self.payload_data.get("id"),
        )
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "creation_time": self.creation_time,
            "property_id": self.extract_property_id(),
            "booking_number": self.extract_booking_number(),
            "payload_keys": sorted(self.payload_data.keys()),
        }
