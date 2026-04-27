# ape-rest-downloader

Small Python CLI for downloading REST device metadata and time-series exports.

This repository was built on top of the [`ape-examples`](https://github.com/archipelagos-labs-com/ape-examples) project and adapts that work into a focused command-line data acquisition workflow.

## Features

- Lists accessible devices
- Lists accessible device profiles
- Fetches time-series device data for one device
- Fetches status time series for one device
- Fetches data for all matching devices across a time range and writes a single CSV export

## Requirements

- Python 3.10+
- Network access to your REST endpoints
- A valid username and API key, and a password if your environment requires it


## Credentials Setup

Create a local credentials file named `api_credentials.txt` in the project root using the example template:

`api_credentials.example.txt` -> `api_credentials.txt`

Then fill in your real values in `api_credentials.txt`.

That local credentials file is ignored by Git and should not be committed.

## Usage

Show all commands:

```bash
python acq.py --help
```

### Fetch all data for a tenant

Use placeholder values like these:

```bash
python acq.py fetch-all-data \
  --start <START_UTC_TIMESTAMP> \
  --end <END_UTC_TIMESTAMP> \
  --tenant-name <TENANT_NAME> \
  --chunk-hours <CHUNK_HOURS> \
  --output-dir <OUTPUT_DIRECTORY>
```

Example parameter meanings:

- `<START_UTC_TIMESTAMP>`: start of the export window, for example `2026-03-01T00:00:00.000000`
- `<END_UTC_TIMESTAMP>`: end of the export window, for example `2026-03-02T23:59:59.999999`
- `<TENANT_NAME>`: tenant filter such as your target tenant name
- `<CHUNK_HOURS>`: chunk size for splitting large requests, for example `24`
- `<OUTPUT_DIRECTORY>`: directory where the combined CSV export should be written, for example `exports`

The generated CSV filename follows this pattern:

```text
ape_export_<start>_<end>.csv
```

### Other commands

List devices:

```bash
python acq.py list-devices --tenant-name <TENANT_NAME>
```

List device profiles:

```bash
python acq.py list-profiles --tenant-id <TENANT_ID>
```

Fetch data for one device:

```bash
python acq.py fetch-data \
  --network-device-id <NETWORK_DEVICE_ID> \
  --start <START_UTC_TIMESTAMP> \
  --end <END_UTC_TIMESTAMP>
```

Fetch status for one device:

```bash
python acq.py fetch-status \
  --network-device-id <NETWORK_DEVICE_ID> \
  --start <START_UTC_TIMESTAMP> \
  --end <END_UTC_TIMESTAMP>
```

## Notes

- Timestamps are expected in UTC ISO-like format.
- `fetch-all-data` requires both `--start` and `--end`.
- Large time ranges may produce large exports, so `--chunk-hours` is useful for keeping requests manageable.
