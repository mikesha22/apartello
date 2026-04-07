from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings

settings = get_settings()


@dataclass(slots=True)
class TTLockToken:
    access_token: str
    expires_at: datetime


class TTLockService:
    def __init__(self) -> None:
        self.base_url = settings.ttlock_api_base_url.rstrip("/")
        self._token_cache: TTLockToken | None = None
        self._tz = ZoneInfo(settings.ttlock_timezone)

    def _validate_settings(self) -> None:
        missing = []
        if not settings.ttlock_client_id:
            missing.append("TTLOCK_CLIENT_ID")
        if not settings.ttlock_client_secret:
            missing.append("TTLOCK_CLIENT_SECRET")
        if not settings.ttlock_username:
            missing.append("TTLOCK_USERNAME")
        if not settings.ttlock_password_md5:
            missing.append("TTLOCK_PASSWORD_MD5")
        if missing:
            raise RuntimeError(f"TTLock is not configured. Missing: {', '.join(missing)}")

    def _now_ms(self) -> int:
        return int(datetime.now(tz=self._tz).timestamp() * 1000)

    def _ensure_tz(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self._tz)
        return dt.astimezone(self._tz)

    def _normalize_start(self, dt: datetime) -> datetime:
        dt = self._ensure_tz(dt)
        return dt.replace(minute=0, second=0, microsecond=0)

    def _normalize_end(self, dt: datetime) -> datetime:
        dt = self._ensure_tz(dt)
        if dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
            return dt
        dt = dt + timedelta(hours=1)
        return dt.replace(minute=0, second=0, microsecond=0)

    async def _post_form(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(f"{self.base_url}{path}", data=data)
            response.raise_for_status()
            payload = response.json()

        if isinstance(payload, dict) and payload.get("errcode") not in (None, 0):
            errmsg = payload.get("errmsg") or payload.get("description") or "Unknown TTLock error"
            raise RuntimeError(f"TTLock error {payload.get('errcode')}: {errmsg}")
        return payload

    async def get_access_token(self, force_refresh: bool = False) -> str:
        self._validate_settings()

        now = datetime.now(tz=self._tz)
        if not force_refresh and self._token_cache and self._token_cache.expires_at > now:
            return self._token_cache.access_token

        payload = await self._post_form(
            "/oauth2/token",
            {
                "client_id": settings.ttlock_client_id,
                "client_secret": settings.ttlock_client_secret,
                "username": settings.ttlock_username,
                "password": settings.ttlock_password_md5,
            },
        )

        access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        # небольшой буфер, чтобы не упереться в пограничное истечение токена
        expires_at = now + timedelta(seconds=max(60, expires_in - 60))
        self._token_cache = TTLockToken(access_token=access_token, expires_at=expires_at)
        return access_token

    async def list_locks(self, page_no: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        access_token = await self.get_access_token()
        payload = await self._post_form(
            "/v3/lock/list",
            {
                "clientId": settings.ttlock_client_id,
                "accessToken": access_token,
                "pageNo": page_no,
                "pageSize": page_size,
                "date": self._now_ms(),
            },
        )
        return payload.get("list", [])

    async def list_passcodes(self, lock_id: int, page_no: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        access_token = await self.get_access_token()
        payload = await self._post_form(
            "/v3/lock/listKeyboardPwd",
            {
                "clientId": settings.ttlock_client_id,
                "accessToken": access_token,
                "lockId": lock_id,
                "pageNo": page_no,
                "pageSize": page_size,
                "date": self._now_ms(),
            },
        )
        return payload.get("list", [])

    async def generate_period_code(
        self,
        *,
        lock_id: int,
        keyboard_pwd_version: int,
        start_at: datetime,
        end_at: datetime,
        keyboard_pwd_name: str | None = None,
    ) -> dict[str, Any]:
        access_token = await self.get_access_token()

        normalized_start = self._normalize_start(start_at)
        normalized_end = self._normalize_end(end_at)
        if normalized_end <= normalized_start:
            raise ValueError("End time must be later than start time")

        payload = await self._post_form(
            "/v3/keyboardPwd/get",
            {
                "clientId": settings.ttlock_client_id,
                "accessToken": access_token,
                "lockId": lock_id,
                "keyboardPwdVersion": keyboard_pwd_version,
                "keyboardPwdType": 3,  # period
                "keyboardPwdName": keyboard_pwd_name or "Guest access code",
                "startDate": int(normalized_start.timestamp() * 1000),
                "endDate": int(normalized_end.timestamp() * 1000),
                "date": self._now_ms(),
            },
        )

        return {
            "keyboard_pwd": payload.get("keyboardPwd"),
            "keyboard_pwd_id": payload.get("keyboardPwdId"),
            "start_at": normalized_start.isoformat(),
            "end_at": normalized_end.isoformat(),
        }
