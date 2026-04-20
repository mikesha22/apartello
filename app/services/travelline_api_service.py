from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings


class TravelLineApiError(RuntimeError):
    pass


class TravelLineApiService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def is_configured(self) -> bool:
        return bool(self.settings.travelline_client_id and self.settings.travelline_client_secret)

    async def get_access_token(self) -> str:
        if not self.is_configured():
            raise TravelLineApiError(
                "TravelLine API credentials are not configured. "
                "Set TRAVELLINE_CLIENT_ID and TRAVELLINE_CLIENT_SECRET."
            )

        if self._access_token and self._access_token_expires_at and datetime.utcnow() < self._access_token_expires_at:
            return self._access_token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.settings.travelline_auth_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.travelline_client_id,
                    "client_secret": self.settings.travelline_client_secret,
                },
            )

        if response.status_code >= 400:
            raise TravelLineApiError(
                f"TravelLine auth failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 3600)

        if not access_token:
            raise TravelLineApiError("TravelLine auth response has no access_token")

        self._access_token = str(access_token)
        self._access_token_expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in - 30, 30))
        return self._access_token

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        url = f"{self.settings.travelline_api_base_url.rstrip('/')}/{path.lstrip('/')}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )

        if response.status_code >= 400:
            raise TravelLineApiError(
                f"TravelLine API request failed [{response.status_code}] {url}: {response.text}"
            )

        data = response.json()
        if not isinstance(data, dict):
            raise TravelLineApiError(f"Unexpected TravelLine API response type for {url}")
        return data

    async def list_booking_summaries(
        self,
        property_id: str,
        *,
        continue_token: str | None = None,
        last_modification: str | None = None,
        count: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "count": count or self.settings.travelline_sync_page_size,
        }
        if continue_token:
            params["continueToken"] = continue_token
        elif last_modification:
            params["lastModification"] = last_modification

        return await self._request_json(
            "GET",
            f"/v1/properties/{property_id}/bookings",
            params=params,
        )

    async def get_booking_details(self, property_id: str, booking_number: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/v1/properties/{property_id}/bookings/{booking_number}",
        )
