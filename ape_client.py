from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

import requests

from api_credentials import ApiCredentials


class ApiError(RuntimeError):
    pass


class ApeRestClient:
    def __init__(
        self,
        credentials: ApiCredentials,
        client_type: str = "python-client",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self._credentials = credentials
        self._client_type = client_type
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._session = requests.Session()

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = self._request_envelope()
        if payload:
            body.update({key: value for key, value in payload.items() if value is not None})

        url = f"{self._credentials.normalized_data_service}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._session.post(url, json=body, timeout=self._timeout)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self._max_retries:
                    raise ApiError(f"API request failed for {path}: {exc}") from exc
                time.sleep(self._retry_delay_seconds * attempt)
                continue

            try:
                data = response.json()
            except ValueError as exc:
                last_error = exc
                response_text = response.text.strip()
                if response.status_code >= 500 and attempt < self._max_retries:
                    time.sleep(self._retry_delay_seconds * attempt)
                    continue
                raise ApiError(
                    f"API returned non-JSON content for {path} "
                    f"(HTTP {response.status_code}): {response_text[:200]}"
                ) from exc

            if response.status_code >= 500:
                last_error = ApiError(f"API returned HTTP {response.status_code}: {data}")
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay_seconds * attempt)
                    continue
                raise last_error

            if not response.ok:
                raise ApiError(f"API returned HTTP {response.status_code}: {data}")

            error_message = data.get("errorMessage")
            if error_message:
                raise ApiError(f"API error for {path}: {error_message}")

            return data

        raise ApiError(f"API request failed for {path}: {last_error}")

    def _request_envelope(self) -> dict[str, Any]:
        return {
            "username": self._credentials.username,
            "apiKey": self._credentials.api_key,
            "clientType": self._client_type,
            "sent": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"),
        }
