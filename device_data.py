from __future__ import annotations

from collections.abc import Iterable
import json
from typing import Any

from ape_client import ApeRestClient


def list_devices(
    client: ApeRestClient,
    *,
    network_name: str | None = None,
    tenant_name: str | None = None,
    device_profile_name: str | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    response = client.post(
        "/v1/device/get",
        {},
    )
    devices = list(response.get("devices", []))

    if tenant_name:
        tenant_needle = tenant_name.casefold()
        devices = [
            device
            for device in devices
            if tenant_needle == str(device.get("properties", {}).get("tenantName", "")).casefold()
        ]

    if network_name:
        network_needle = network_name.casefold()
        devices = [
            device
            for device in devices
            if network_needle == str(device.get("properties", {}).get("networkName", "")).casefold()
        ]

    if device_profile_name:
        target = device_profile_name.casefold()
        devices = [
            device
            for device in devices
            if str(device.get("properties", {}).get("deviceProfileName", "")).casefold() == target
        ]

    if name_contains:
        needle = name_contains.casefold()
        devices = [
            device
            for device in devices
            if needle in str(device.get("name", "")).casefold()
            or needle in str(device.get("networkDeviceId", "")).casefold()
            or needle in str(device.get("properties", {}).get("locationId", "")).casefold()
        ]

    devices.sort(key=lambda device: str(device.get("networkDeviceId", "")))
    if limit is not None:
        devices = devices[:limit]
    return devices


def list_device_profiles(
    client: ApeRestClient,
    *,
    tenant_id: str | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    response = client.post("/v1/device-profile/get", {"tenantId": tenant_id})
    profiles = list(response.get("deviceProfiles", []))

    if name_contains:
        needle = name_contains.casefold()
        profiles = [
            profile
            for profile in profiles
            if needle in str(profile.get("name", "")).casefold()
        ]

    profiles.sort(key=lambda profile: str(profile.get("name", "")))
    if limit is not None:
        profiles = profiles[:limit]
    return profiles


def get_device_data(
    client: ApeRestClient,
    *,
    network_device_id: str,
    fields: Iterable[str] | None = None,
    network_id: str | None = None,
    network_name: str | None = None,
    tenant_id: str | None = None,
    tenant_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
    max_entries: int | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    return client.post(
        "/v1/device/data/get",
        {
            "networkDeviceId": network_device_id,
            "fields": _clean_fields(fields),
            "networkId": network_id,
            "networkName": network_name,
            "tenantId": tenant_id,
            "tenantName": tenant_name,
            "start": start,
            "end": end,
            "maxEntries": max_entries,
            "order": order,
        },
    )


def get_device_status(
    client: ApeRestClient,
    *,
    network_device_id: str,
    fields: Iterable[str] | None = None,
    network_id: str | None = None,
    network_name: str | None = None,
    tenant_id: str | None = None,
    tenant_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
    max_entries: int | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    return client.post(
        "/v1/device/status/get",
        {
            "networkDeviceId": network_device_id,
            "fields": _clean_fields(fields),
            "networkId": network_id,
            "networkName": network_name,
            "tenantId": tenant_id,
            "tenantName": tenant_name,
            "start": start,
            "end": end,
            "maxEntries": max_entries,
            "order": order,
        },
    )


def flatten_device_rows(devices: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for device in devices:
        row = {
            "deviceId": device.get("deviceId"),
            "networkDeviceId": device.get("networkDeviceId"),
            "name": device.get("name"),
            "description": device.get("description"),
            "tenantId": device.get("tenantId"),
            "deviceProfileId": device.get("deviceProfileId"),
            "createdAt": device.get("createdAt"),
            "updatedAt": device.get("updatedAt"),
            "location": json.dumps(device.get("location", [])),
        }
        for key, value in sorted((device.get("properties") or {}).items()):
            row[f"property_{key}"] = value
        rows.append(row)
    return rows


def flatten_profile_rows(profiles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in profiles:
        row = {
            "deviceProfileId": profile.get("deviceProfileId"),
            "name": profile.get("name"),
            "description": profile.get("description"),
            "tenantId": profile.get("tenantId"),
            "createdAt": profile.get("createdAt"),
            "updatedAt": profile.get("updatedAt"),
            "payloadFields": json.dumps(profile.get("payloadFields", [])),
            "properties": json.dumps(profile.get("properties", {})),
        }
        rows.append(row)
    return rows


def flatten_time_series_rows(
    response: dict[str, Any],
    *,
    reverse: bool = False,
) -> list[dict[str, Any]]:
    rows_by_timestamp: dict[str, dict[str, Any]] = {}
    for series in response.get("timeSeries", []):
        field_name = series.get("name", "unknown")
        for point in series.get("data", []):
            timestamp = point.get("timestamp")
            if not timestamp:
                continue
            row = rows_by_timestamp.setdefault(timestamp, {"timestamp": timestamp})
            row[field_name] = point.get("value")

    timestamps = sorted(rows_by_timestamp, reverse=reverse)
    return [rows_by_timestamp[timestamp] for timestamp in timestamps]


def flatten_device_time_series_rows(
    response: dict[str, Any],
    device: dict[str, Any],
    *,
    reverse: bool = False,
) -> list[dict[str, Any]]:
    properties = device.get("properties") or {}
    base_row = {
        "deviceId": device.get("deviceId"),
        "networkDeviceId": device.get("networkDeviceId"),
        "deviceName": device.get("name"),
        "tenantId": device.get("tenantId"),
        "tenantName": properties.get("tenantName"),
        "deviceProfileId": device.get("deviceProfileId"),
        "deviceProfileName": properties.get("deviceProfileName"),
        "locationId": properties.get("locationId"),
    }

    rows = flatten_time_series_rows(response, reverse=reverse)
    return [{**base_row, **row} for row in rows]


def summarize_devices(devices: Iterable[dict[str, Any]], limit: int = 10) -> str:
    lines = []
    for device in list(devices)[:limit]:
        properties = device.get("properties") or {}
        lines.append(
            " | ".join(
                [
                    str(device.get("networkDeviceId", "")),
                    str(device.get("name", "")),
                    str(properties.get("tenantName", "")),
                    str(properties.get("deviceProfileName", "")),
                    str(properties.get("locationId", "")),
                ]
            )
        )
    return "\n".join(lines)


def summarize_profiles(profiles: Iterable[dict[str, Any]], limit: int = 10) -> str:
    lines = []
    for profile in list(profiles)[:limit]:
        payload_fields = profile.get("payloadFields") or []
        lines.append(
            " | ".join(
                [
                    str(profile.get("name", "")),
                    str(profile.get("tenantId", "")),
                    str(len(payload_fields)),
                ]
            )
        )
    return "\n".join(lines)


def summarize_time_series(rows: Iterable[dict[str, Any]], limit: int = 10) -> str:
    lines = []
    for row in list(rows)[:limit]:
        parts = [f"{key}={value}" for key, value in row.items()]
        lines.append(", ".join(parts))
    return "\n".join(lines)


def _clean_fields(fields: Iterable[str] | None) -> list[str] | None:
    if fields is None:
        return None
    cleaned = [field.strip() for field in fields if field and field.strip()]
    return cleaned or None
