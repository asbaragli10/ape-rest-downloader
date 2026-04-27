from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class ApiCredentials:
    username: str
    password: str | None
    api_key: str
    data_service: str
    streaming_service: str | None = None

    @property
    def normalized_data_service(self) -> str:
        return self.data_service.rstrip("/")


def load_credentials(credentials_file: str | Path) -> ApiCredentials:
    path = Path(credentials_file)
    text = path.read_text(encoding="utf-8")

    username = _extract(r"^Username:\s*(.+?)\s*$", text, "Username")
    password = _extract(r"^Password:\s*(.+?)\s*$", text, "Password", required=False)
    api_key = _extract(r"^API Key:\s*(.+?)\s*$", text, "API Key")
    data_service = _extract(r'^data_service\s*=\s*"(.+?)"\s*$', text, "data_service")
    streaming_service = _extract(
        r'^streaming_service\s*=\s*"(.+?)"\s*$',
        text,
        "streaming_service",
        required=False,
    )

    return ApiCredentials(
        username=username,
        password=password,
        api_key=api_key,
        data_service=data_service,
        streaming_service=streaming_service,
    )


def _extract(pattern: str, text: str, label: str, required: bool = True) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    if required:
        raise ValueError(f"Could not find '{label}' in the credentials file.")
    return None
