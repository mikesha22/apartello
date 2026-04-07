from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Booking
from app.services.ttlock_mapping_service import TTLockMappingService
from app.services.ttlock_service import TTLockService

router = APIRouter(prefix="/ttlock", tags=["ttlock"])


ttlock_service = TTLockService()
mapping_service = TTLockMappingService()


class ManualGenerateCodeIn(BaseModel):
    lock_id: int
    keyboard_pwd_version: int
    start_at: datetime
    end_at: datetime
    keyboard_pwd_name: str | None = None


class BookingGenerateCodeIn(BaseModel):
    external_booking_id: str


@router.get("/locks")
async def ttlock_list_locks():
    locks = await ttlock_service.list_locks()
    return {"ok": True, "locks": locks}


@router.get("/locks/{lock_id}/passcodes")
async def ttlock_list_passcodes(lock_id: int):
    codes = await ttlock_service.list_passcodes(lock_id)
    return {"ok": True, "passcodes": codes}


@router.post("/generate-period-code")
async def ttlock_generate_period_code(payload: ManualGenerateCodeIn):
    result = await ttlock_service.generate_period_code(
        lock_id=payload.lock_id,
        keyboard_pwd_version=payload.keyboard_pwd_version,
        start_at=payload.start_at,
        end_at=payload.end_at,
        keyboard_pwd_name=payload.keyboard_pwd_name,
    )
    return {"ok": True, **result}


@router.post("/generate-period-code-by-booking")
async def ttlock_generate_period_code_by_booking(
    payload: BookingGenerateCodeIn,
    db: Session = Depends(get_db),
):
    booking = db.scalar(
        select(Booking).where(Booking.external_booking_id == payload.external_booking_id)
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.checkin_at is None or booking.checkout_at is None:
        raise HTTPException(status_code=400, detail="Booking has no check-in/check-out dates")

    mapping = mapping_service.get_lock_mapping(booking.property_name, booking.room_name)
    if mapping is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "No TTLock mapping found for this booking. "
                "Fill LOCK_MAPPINGS in app/services/ttlock_mapping_service.py"
            ),
        )

    result = await ttlock_service.generate_period_code(
        lock_id=mapping.lock_id,
        keyboard_pwd_version=mapping.keyboard_pwd_version,
        start_at=booking.checkin_at,
        end_at=booking.checkout_at,
        keyboard_pwd_name=f"Guest {booking.external_booking_id}",
    )

    return {
        "ok": True,
        "external_booking_id": booking.external_booking_id,
        "property_name": booking.property_name,
        "room_name": booking.room_name,
        "lock_id": mapping.lock_id,
        **result,
    }
