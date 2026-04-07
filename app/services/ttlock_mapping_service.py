from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LockBinding


@dataclass(slots=True)
class LockMapping:
    lock_id: int
    keyboard_pwd_version: int
    lock_alias: str | None = None
    binding_id: int | None = None


# Fallback for emergency/manual mode.
# Primary source of truth is the lock_bindings table.
LOCK_MAPPINGS: dict[tuple[str, str], LockMapping] = {
    # ("Apartello Tolstogo", "Апартамент 12"): LockMapping(
    #     lock_id=123456,
    #     keyboard_pwd_version=4,
    #     lock_alias="Tolstogo 12",
    # ),
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


class TTLockMappingService:
    def get_lock_mapping(
        self,
        property_name: str | None,
        room_name: str | None,
        db: Session | None = None,
    ) -> LockMapping | None:
        if db is not None:
            binding = self.get_lock_binding(db, property_name, room_name)
            if binding is not None:
                return LockMapping(
                    lock_id=binding.lock_id,
                    keyboard_pwd_version=binding.keyboard_pwd_version,
                    lock_alias=binding.lock_alias,
                    binding_id=binding.id,
                )

        key = (_normalize(property_name), _normalize(room_name))
        for (mapping_property, mapping_room), mapping in LOCK_MAPPINGS.items():
            if (_normalize(mapping_property), _normalize(mapping_room)) == key:
                return mapping
        return None

    def get_lock_binding(
        self,
        db: Session,
        property_name: str | None,
        room_name: str | None,
    ) -> LockBinding | None:
        if not property_name or not room_name:
            return None

        stmt = select(LockBinding).where(
            LockBinding.is_active.is_(True),
            func.lower(func.trim(LockBinding.property_name)) == _normalize(property_name),
            func.lower(func.trim(LockBinding.room_name)) == _normalize(room_name),
        )
        return db.scalar(stmt)

    def upsert_lock_binding(
        self,
        db: Session,
        *,
        property_name: str,
        room_name: str,
        lock_id: int,
        keyboard_pwd_version: int,
        lock_alias: str | None = None,
        is_active: bool = True,
    ) -> LockBinding:
        existing = self.get_lock_binding(db, property_name, room_name)
        if existing is None:
            existing = db.scalar(
                select(LockBinding).where(
                    func.lower(func.trim(LockBinding.property_name)) == _normalize(property_name),
                    func.lower(func.trim(LockBinding.room_name)) == _normalize(room_name),
                )
            )

        if existing is None:
            existing = LockBinding(
                property_name=property_name.strip(),
                room_name=room_name.strip(),
                lock_id=lock_id,
                keyboard_pwd_version=keyboard_pwd_version,
                lock_alias=lock_alias,
                is_active=is_active,
            )
            db.add(existing)
        else:
            existing.property_name = property_name.strip()
            existing.room_name = room_name.strip()
            existing.lock_id = lock_id
            existing.keyboard_pwd_version = keyboard_pwd_version
            existing.lock_alias = lock_alias
            existing.is_active = is_active

        db.commit()
        db.refresh(existing)
        return existing
