from dataclasses import dataclass


@dataclass(slots=True)
class LockMapping:
    lock_id: int
    keyboard_pwd_version: int
    lock_alias: str | None = None


# TODO:
# Заполни реальные lock_id и keyboard_pwd_version после вызова /ttlock/locks
# Ключ словаря: (property_name, room_name)
LOCK_MAPPINGS: dict[tuple[str, str], LockMapping] = {
    # Пример:
    # ("Apartello Tolstogo", "Апартамент 12"): LockMapping(
    #     lock_id=123456,
    #     keyboard_pwd_version=4,
    #     lock_alias="Tolstogo 12",
    # ),
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


class TTLockMappingService:
    def get_lock_mapping(self, property_name: str | None, room_name: str | None) -> LockMapping | None:
        key = (_normalize(property_name), _normalize(room_name))

        for (mapping_property, mapping_room), mapping in LOCK_MAPPINGS.items():
            if (_normalize(mapping_property), _normalize(mapping_room)) == key:
                return mapping
        return None
