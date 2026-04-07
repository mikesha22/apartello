from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Booking, LockBinding
from app.services.access_code_service import AccessCodeService
from app.services.ttlock_mapping_service import TTLockMappingService
from app.services.ttlock_service import TTLockService

router = APIRouter(prefix="/ttlock", tags=["ttlock"])


ttlock_service = TTLockService()
mapping_service = TTLockMappingService()
access_code_service = AccessCodeService()


class ManualGenerateCodeIn(BaseModel):
    lock_id: int
    keyboard_pwd_version: int
    start_at: datetime
    end_at: datetime
    keyboard_pwd_name: str | None = None


class BookingGenerateCodeIn(BaseModel):
    external_booking_id: str


class LockBindingIn(BaseModel):
    property_name: str
    room_name: str
    lock_id: int
    keyboard_pwd_version: int
    lock_alias: str | None = None
    is_active: bool = True


@router.get("/locks")
async def ttlock_list_locks():
    locks = await ttlock_service.list_locks()
    return {"ok": True, "locks": locks}


@router.get("/locks/{lock_id}/passcodes")
async def ttlock_list_passcodes(lock_id: int):
    codes = await ttlock_service.list_passcodes(lock_id)
    return {"ok": True, "passcodes": codes}


@router.get("/lock-bindings")
def list_lock_bindings(db: Session = Depends(get_db)):
    bindings = db.scalars(select(LockBinding).order_by(LockBinding.property_name, LockBinding.room_name)).all()
    return {
        "ok": True,
        "items": [
            {
                "id": item.id,
                "property_name": item.property_name,
                "room_name": item.room_name,
                "lock_id": item.lock_id,
                "keyboard_pwd_version": item.keyboard_pwd_version,
                "lock_alias": item.lock_alias,
                "is_active": item.is_active,
            }
            for item in bindings
        ],
    }


@router.post("/lock-bindings")
def upsert_lock_binding(payload: LockBindingIn, db: Session = Depends(get_db)):
    binding = mapping_service.upsert_lock_binding(
        db,
        property_name=payload.property_name,
        room_name=payload.room_name,
        lock_id=payload.lock_id,
        keyboard_pwd_version=payload.keyboard_pwd_version,
        lock_alias=payload.lock_alias,
        is_active=payload.is_active,
    )
    return {
        "ok": True,
        "binding": {
            "id": binding.id,
            "property_name": binding.property_name,
            "room_name": binding.room_name,
            "lock_id": binding.lock_id,
            "keyboard_pwd_version": binding.keyboard_pwd_version,
            "lock_alias": binding.lock_alias,
            "is_active": binding.is_active,
        },
    }


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

    try:
        code = await access_code_service.ensure_code_for_booking(db, booking)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "ok": True,
        "external_booking_id": booking.external_booking_id,
        "property_name": booking.property_name,
        "room_name": booking.room_name,
        "keyboard_pwd": code.keyboard_pwd,
        "keyboard_pwd_id": code.keyboard_pwd_id,
        "valid_from": code.valid_from.isoformat(),
        "valid_to": code.valid_to.isoformat(),
        "reveal_from": code.reveal_from.isoformat(),
        "status": code.status,
    }


@router.get("/access-codes/{external_booking_id}")
def get_access_code_by_booking(external_booking_id: str, db: Session = Depends(get_db)):
    booking = db.scalar(select(Booking).where(Booking.external_booking_id == external_booking_id))
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    code = access_code_service.get_latest_code(db, booking.id)
    if code is None:
        return {"ok": True, "external_booking_id": booking.external_booking_id, "access_code": None}

    return {
        "ok": True,
        "external_booking_id": booking.external_booking_id,
        "access_code": {
            "id": code.id,
            "status": code.status,
            "keyboard_pwd": code.keyboard_pwd,
            "keyboard_pwd_id": code.keyboard_pwd_id,
            "valid_from": code.valid_from.isoformat(),
            "valid_to": code.valid_to.isoformat(),
            "reveal_from": code.reveal_from.isoformat(),
            "delivered_at": code.delivered_at.isoformat() if code.delivered_at else None,
            "last_error": code.last_error,
        },
    }
