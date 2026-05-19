# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-05-19

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
- Configuration file support: `WICAN_URL` env var, `./wican-cli.yaml`, `~/.config/wican-cli/config.yaml`
- Named device aliases (`--wican home`, `--wican vpn`, etc.)
- Path traversal protection on file downloads
- Input validation for voltage, time, and limit parameters
- `--json` output on `config`, `status`, `logs`, and `autopid` commands

[0.1.0]: https://github.com/philipkocanda/wican-cli/releases/tag/v0.1.0
