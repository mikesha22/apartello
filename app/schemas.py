from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class TelegramUserSchema(BaseModel):
    id: int
    first_name: str | None = None
    username: str | None = None


class TelegramChatSchema(BaseModel):
    id: int
    type: str


class TelegramMessageSchema(BaseModel):
    message_id: int
    text: str | None = None
    chat: TelegramChatSchema
    from_: TelegramUserSchema | None = Field(default=None, alias="from")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TelegramUpdateSchema(BaseModel):
    update_id: int
    message: TelegramMessageSchema | None = None


class BookingOut(BaseModel):
    id: int
    external_booking_id: str
    status: str | None = None
    property_name: str | None = None
    room_name: str | None = None
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
