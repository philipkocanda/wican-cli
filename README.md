# wican-cli

Command-line tool for managing [WiCAN Pro](https://github.com/meatpiHQ/wican-fw) OBD-II WiFi devices.

View and save device configuration, toggle sleep mode, switch protocol modes, query SD card logs, check AutoPID values, and reboot — all from your terminal.

## Installation

```bash
pip install wican-cli
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install wican-cli
```

## Quick start

```bash
# Connect to WiCAN on its default AP address (192.168.80.1)
wican status

# Or specify a device address
wican --wican 10.0.2.86 status

# Set up a config file to avoid typing the address every time
mkdir -p ~/.config/wican-cli
cat > ~/.config/wican-cli/config.yaml << 'EOF'
wican_addresses:
  home: "10.0.2.86"
  vpn: "192.168.3.2"
default_wican: home
EOF

# Now just use the named alias
wican status
wican --wican vpn status
```

## Commands

| Command | Description |
|---------|-------------|
| `wican config` | View device configuration (optionally save to file) |
| `wican sleep` | View or modify sleep/power settings |
| `wican status` | Device status summary |
| `wican protocol` | View or switch CAN protocol mode |
| `wican logs` | List, download, or query SD card OBD log databases |
| `wican autopid` | Show latest AutoPID cached values |
| `wican reboot` | Reboot the device |

### Examples

```bash
# Save a config snapshot with credentials stripped
wican config --save --redact

# Enable sleep mode with 12.5V threshold
wican sleep --enable --voltage 12.5

# Switch to ELM327 mode for use with Torque/Car Scanner
wican protocol --set elm327

# Download all log databases from the SD card
wican logs --download

# Query a specific parameter from the latest log
wican logs --query SOC_BMS --limit 20

# Show AutoPID values filtered by name
wican autopid -f tyre
```

## Configuration

wican-cli looks for configuration in this order:

1. `WICAN_URL` environment variable (overrides everything)
2. `./wican-cli.yaml` (project-local)
3. `~/.config/wican-cli/config.yaml` (user-global)

If none is found, it defaults to `192.168.80.1` (WiCAN's built-in AP).

### Config file format

```yaml
wican_addresses:
  home: "10.0.2.86"       # Device on local LAN
  vpn: "192.168.3.2"      # Device via VPN tunnel
  ap: "192.168.80.1"      # Direct AP connection
default_wican: home        # Which address to use by default
```

Use `--wican <name>` to select a different address, or pass an IP/URL directly: `--wican 192.168.1.100`.

## Global flags

| Flag | Description |
|------|-------------|
| `--wican ADDR` | Device address: named alias or IP/URL |
| `--timeout SEC` | Request timeout in seconds (default: 10) |
| `--version` | Show version and exit |

## What is WiCAN?

[WiCAN Pro](https://github.com/meatpiHQ/wican-fw) is an ESP32-based WiFi/BLE OBD-II adapter that supports multiple protocols (AutoPID, SLCAN, ELM327, SavvyCAN, RealDash). It can publish vehicle data via MQTT to Home Assistant, log to SD card, and provide a WebSocket terminal interface.

This CLI tool manages the device itself — it does not send CAN/OBD requests to the vehicle. For that, use tools like [python-can](https://github.com/hardbyte/python-can), [SavvyCAN](https://github.com/collin80/SavvyCAN), or [Torque](https://torque-bhp.com/).

## License

Public domain — see [LICENSE](LICENSE) (Unlicense).
