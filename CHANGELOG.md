# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-19

### Added

- Protocol aliases: `autopid` resolves to `auto_pid`, `realdash` to `realdash66`
- Protocol switch warnings explaining consequences of leaving/entering each mode
- Rich protocol display with active marker, port info, and alias listing
- Log list shows `(active)` marker and human-readable file sizes
- AutoPID header: "AutoPID data — N parameters" with filter indicator
- `can` config section showing `can_datarate`, `can_mode`, `protocol`
- `py.typed` marker (PEP 561) for downstream type checking
- CI/CD with GitHub Actions: ruff lint + format check, pytest matrix (3.10–3.13)
- Local caching of downloaded log databases (`~/.cache/wican/logs/`)
- Corruption-tolerant log queries with tiered fallback (graceful degradation)

### Changed

- Renamed project-local config file from `wican-cli.yaml` to `config.yaml`
- Refactored CLI into per-feature command modules (`commands/` package)
- Status output now shows grouped sections (Device, Network, CAN/OBD, Power, MQTT, Logging)
- Removed misleading SSID fields from status output (firmware doesn't expose connected SSID)

### Fixed

- `wican pids`: 404 error — corrected endpoint from `/check_autopids` to `/autopid_data`
- `wican logs`: 404 error — corrected endpoint from `/list_files` to `/obd_logs`
- Log download endpoint corrected from `/download_file?name=` to `/obd_logs/{filename}`
- Log query: fixed `no such table: obd_data` — uses correct schema (`param_info`/`param_data`)
- Battery voltage no longer doubled (e.g. "12.4VV") when firmware already includes suffix
- CI: dev dependencies (pytest, ruff) not installed during workflow runs

## [0.1.0] - 2026-05-19

### Added

- Initial release
- `wican config` — view and save device configuration snapshots
  - `--save` saves to `configs/` with date-stamped filename (never overwrites)
  - `--redact` strips credentials from saved snapshots
  - `--section` filters to specific config sections (sleep, mqtt, wifi, etc.)
- `wican sleep` — view and modify sleep/power settings
- `wican status` — device status summary
- `wican protocol` — view or switch CAN protocol mode (auto_pid, elm327, slcan, etc.)
- `wican logs` — list, download, and query SD card OBD log databases
  - `--download` fetches all logs to local `logs/` directory
  - `--query PARAM` queries SQLite log databases
  - `--params` lists all logged parameter names
- `wican autopid` — show latest AutoPID cached values with optional filter
- `wican reboot` — reboot the device
- Configuration file support: `WICAN_URL` env var, `./config.yaml`, `~/.config/wican-cli/config.yaml`
- Named device aliases (`--wican home`, `--wican vpn`, etc.)
- Path traversal protection on file downloads
- Input validation for voltage, time, and limit parameters
- `--json` output on `config`, `status`, `logs`, and `autopid` commands

[unreleased]: https://github.com/philipkocanda/wican-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/philipkocanda/wican-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/philipkocanda/wican-cli/releases/tag/v0.1.0
