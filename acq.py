from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

from ape_client import ApeRestClient, ApiError
from api_credentials import load_credentials
from data_export import write_csv, write_json
from device_data import (
    flatten_device_rows,
    flatten_device_time_series_rows,
    flatten_profile_rows,
    flatten_time_series_rows,
    get_device_data,
    get_device_status,
    list_device_profiles,
    list_devices,
    summarize_devices,
    summarize_profiles,
    summarize_time_series,
)


DEFAULT_CREDENTIALS_FILE = Path("api_credentials.txt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="REST acquisition workflow built around the live APE device endpoints."
    )
    parser.add_argument(
        "--credentials-file",
        default=str(DEFAULT_CREDENTIALS_FILE),
        help="Path to the API credentials file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for each API request.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    devices_parser = subparsers.add_parser(
        "list-devices",
        help="List accessible devices and optionally export the result.",
    )
    devices_parser.add_argument("--network-name")
    devices_parser.add_argument("--tenant-name")
    devices_parser.add_argument("--device-profile-name")
    devices_parser.add_argument("--name-contains")
    devices_parser.add_argument("--limit", type=int)
    devices_parser.add_argument("--output-json")
    devices_parser.add_argument("--output-csv")

    profiles_parser = subparsers.add_parser(
        "list-profiles",
        help="List accessible device profiles and optionally export the result.",
    )
    profiles_parser.add_argument("--tenant-id")
    profiles_parser.add_argument("--name-contains")
    profiles_parser.add_argument("--limit", type=int)
    profiles_parser.add_argument("--output-json")
    profiles_parser.add_argument("--output-csv")

    all_data_parser = subparsers.add_parser(
        "fetch-all-data",
        help="Fetch data for all accessible devices over a time range and export one CSV.",
    )
    all_data_parser.add_argument(
        "--start",
        required=True,
        help="UTC start timestamp, for example 2026-03-31T00:00:00.000000",
    )
    all_data_parser.add_argument(
        "--end",
        required=True,
        help="UTC end timestamp, for example 2026-03-31T23:59:59.999999",
    )
    all_data_parser.add_argument(
        "--fields",
        nargs="+",
        help="Optional list of fields to request. Separate multiple names with spaces.",
    )
    all_data_parser.add_argument("--network-name")
    all_data_parser.add_argument("--tenant-name")
    all_data_parser.add_argument(
        "--chunk-hours",
        type=int,
        default=24,
        help="Split the requested time range into smaller windows to avoid oversized pulls.",
    )
    all_data_parser.add_argument(
        "--max-entries",
        type=int,
        help="Optional server-side cap for each device request inside each chunk.",
    )
    all_data_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the generated ape_export_<start>_<end>.csv file should be written.",
    )

    data_parser = _build_time_series_parser(
        subparsers,
        "fetch-data",
        "Fetch device time-series data and optionally export it.",
    )
    status_parser = _build_time_series_parser(
        subparsers,
        "fetch-status",
        "Fetch device status time series and optionally export it.",
    )

    data_parser.set_defaults(handler=handle_fetch_data)
    status_parser.set_defaults(handler=handle_fetch_status)
    devices_parser.set_defaults(handler=handle_list_devices)
    profiles_parser.set_defaults(handler=handle_list_profiles)
    all_data_parser.set_defaults(handler=handle_fetch_all_data)

    return parser


def _build_time_series_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--network-device-id", required=True)
    parser.add_argument(
        "--fields",
        nargs="+",
        help="Optional list of fields to request. Separate multiple names with spaces.",
    )
    parser.add_argument("--network-id")
    parser.add_argument("--network-name")
    parser.add_argument("--tenant-id")
    parser.add_argument("--tenant-name")
    parser.add_argument("--start", help="UTC start timestamp, for example 2026-03-31T00:00:00.000000")
    parser.add_argument("--end", help="UTC end timestamp, for example 2026-03-31T23:59:59.999999")
    parser.add_argument("--max-entries", type=int)
    parser.add_argument("--order", choices=("asc", "desc"), default="desc")
    parser.add_argument("--output-json")
    parser.add_argument("--output-csv")
    return parser


def handle_list_devices(args: argparse.Namespace, client: ApeRestClient) -> int:
    devices = list_devices(
        client,
        network_name=args.network_name,
        tenant_name=args.tenant_name,
        device_profile_name=args.device_profile_name,
        name_contains=args.name_contains,
        limit=args.limit,
    )
    _maybe_export_raw_and_rows(
        raw_data={"devices": devices},
        rows=flatten_device_rows(devices),
        output_json=args.output_json,
        output_csv=args.output_csv,
    )

    print(f"Devices returned: {len(devices)}")
    if devices:
        print("networkDeviceId | name | tenantName | deviceProfileName | locationId")
        print(summarize_devices(devices))
    return 0


def handle_list_profiles(args: argparse.Namespace, client: ApeRestClient) -> int:
    profiles = list_device_profiles(
        client,
        tenant_id=args.tenant_id,
        name_contains=args.name_contains,
        limit=args.limit,
    )
    _maybe_export_raw_and_rows(
        raw_data={"deviceProfiles": profiles},
        rows=flatten_profile_rows(profiles),
        output_json=args.output_json,
        output_csv=args.output_csv,
    )

    print(f"Profiles returned: {len(profiles)}")
    if profiles:
        print("name | tenantId | payload_field_count")
        print(summarize_profiles(profiles))
    return 0


def handle_fetch_data(args: argparse.Namespace, client: ApeRestClient) -> int:
    response = get_device_data(
        client,
        network_device_id=args.network_device_id,
        fields=args.fields,
        network_id=args.network_id,
        network_name=args.network_name,
        tenant_id=args.tenant_id,
        tenant_name=args.tenant_name,
        start=args.start,
        end=args.end,
        max_entries=args.max_entries,
        order=args.order,
    )
    return _handle_time_series_response(response, args)


def handle_fetch_status(args: argparse.Namespace, client: ApeRestClient) -> int:
    response = get_device_status(
        client,
        network_device_id=args.network_device_id,
        fields=args.fields,
        network_id=args.network_id,
        network_name=args.network_name,
        tenant_id=args.tenant_id,
        tenant_name=args.tenant_name,
        start=args.start,
        end=args.end,
        max_entries=args.max_entries,
        order=args.order,
    )
    return _handle_time_series_response(response, args)


def handle_fetch_all_data(args: argparse.Namespace, client: ApeRestClient) -> int:
    if args.chunk_hours <= 0:
        raise ValueError("--chunk-hours must be greater than zero.")

    start_dt = _parse_timestamp(args.start)
    end_dt = _parse_timestamp(args.end)
    if end_dt < start_dt:
        raise ValueError("--end must be greater than or equal to --start.")

    devices = list_devices(
        client,
        network_name=args.network_name,
        tenant_name=args.tenant_name,
    )
    if not devices:
        print("No devices matched the requested filters.")
        return 0

    windows = _build_time_windows(start_dt, end_dt, args.chunk_hours)
    all_rows: list[dict] = []

    print(f"Devices to fetch: {len(devices)}")
    print(f"Time windows to fetch per device: {len(windows)}")

    for device_index, device in enumerate(devices, start=1):
        network_device_id = device.get("networkDeviceId")
        device_name = device.get("name", "")
        print(f"[{device_index}/{len(devices)}] Fetching {network_device_id} ({device_name})")

        for window_start, window_end in windows:
            response = get_device_data(
                client,
                network_device_id=str(network_device_id),
                fields=args.fields,
                network_name=args.network_name,
                tenant_name=args.tenant_name,
                start=_format_timestamp(window_start),
                end=_format_timestamp(window_end),
                max_entries=args.max_entries,
                order="asc",
            )
            all_rows.extend(
                flatten_device_time_series_rows(
                    response,
                    device,
                    reverse=False,
                )
            )

    all_rows.sort(key=lambda row: (str(row.get("networkDeviceId", "")), str(row.get("timestamp", ""))))

    output_name = _build_export_name(args.start, args.end)
    output_path = Path(args.output_dir) / output_name
    write_csv(output_path, all_rows)

    print(f"Combined rows written: {len(all_rows)}")
    print(f"CSV written to {output_path}")
    return 0


def _handle_time_series_response(response: dict, args: argparse.Namespace) -> int:
    rows = flatten_time_series_rows(response, reverse=(args.order == "desc"))
    _maybe_export_raw_and_rows(
        raw_data=response,
        rows=rows,
        output_json=args.output_json,
        output_csv=args.output_csv,
    )

    print(f"Series returned: {len(response.get('timeSeries', []))}")
    print(f"Rows after flattening: {len(rows)}")
    if rows:
        print(summarize_time_series(rows))
    return 0


def _maybe_export_raw_and_rows(
    *,
    raw_data: dict,
    rows: list[dict],
    output_json: str | None,
    output_csv: str | None,
) -> None:
    if output_json:
        target = write_json(output_json, raw_data)
        print(f"JSON written to {target}")
    if output_csv:
        target = write_csv(output_csv, rows)
        print(f"CSV written to {target}")


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _build_time_windows(
    start_dt: datetime,
    end_dt: datetime,
    chunk_hours: int,
) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start_dt
    chunk = timedelta(hours=chunk_hours)
    step = timedelta(microseconds=1)

    while cursor <= end_dt:
        window_end = min(cursor + chunk - step, end_dt)
        windows.append((cursor, window_end))
        cursor = window_end + step

    return windows


def _build_export_name(start_text: str, end_text: str) -> str:
    start_fragment = _safe_filename_fragment(start_text)
    end_fragment = _safe_filename_fragment(end_text)
    return f"ape_export_{start_fragment}_{end_fragment}.csv"


def _safe_filename_fragment(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "-", value.strip())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        credentials = load_credentials(args.credentials_file)
        client = ApeRestClient(credentials, timeout=args.timeout)
        return args.handler(args, client)
    except (OSError, ValueError, ApiError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
