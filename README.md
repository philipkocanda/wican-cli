# wican-cli

Command-line tool for managing [WiCAN Pro](https://github.com/meatpiHQ/wican-fw) OBD-II WiFi devices.

View and save device configuration, toggle sleep mode, switch protocol modes, query SD card logs, check AutoPID values, and reboot — all from your terminal.

<img width="464" height="740" alt="Screenshot 2026-05-19 at 21 36 38" src="https://github.com/user-attachments/assets/30948c2a-ffc2-4486-b6e0-5d456c4b5a33" />

<img width="425" height="523" alt="Screenshot 2026-05-19 at 21 30 26" src="https://github.com/user-attachments/assets/ca4b8e04-7c5a-432a-8e07-c54088ab632f" />



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
wican --wican 192.168.1.100 status

# Set up a config file to avoid typing the address every time
mkdir -p ~/.config/wican-cli
cat > ~/.config/wican-cli/config.yaml << 'EOF'
wican_addresses:
  home: "192.168.1.100"
  vpn: "10.8.0.50"
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
2. `./config.yaml` (project-local)
3. `~/.config/wican-cli/config.yaml` (user-global)

If none is found, it defaults to `192.168.80.1` (WiCAN's built-in AP).

### Config file format

```yaml
wican_addresses:
  home: "192.168.1.100"    # Device on local LAN
  vpn: "10.8.0.50"         # Device via VPN tunnel
  ap: "192.168.80.1"       # Direct AP connection (WiCAN default)
default_wican: home         # Which address to use by default
```

Use `--wican <name>` to select a different address, or pass an IP/URL directly: `--wican 192.168.1.100`.

## Global flags

| Flag | Description |
|------|-------------|
| `--wican ADDR` | Device address: named alias or IP/URL |
| `--timeout SEC` | Request timeout in seconds (default: 10) |
| `--json` | JSON output (available on most commands) |
| `--version` | Show version and exit |

## Shell completions

wican-cli uses [argcomplete](https://github.com/kislyuk/argcomplete) for tab completions in bash, zsh, and fish.

### Global activation (all argcomplete-enabled tools)

```bash
# bash (add to ~/.bashrc)
activate-global-python-argcomplete

# zsh (add to ~/.zshrc)
autoload -U bashcompinit && bashcompinit
activate-global-python-argcomplete

# fish
register-python-argcomplete --shell fish wican | source
```

### Per-command activation

```bash
# bash (add to ~/.bashrc)
eval "$(register-python-argcomplete wican)"

# zsh (add to ~/.zshrc)
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete wican)"

# fish (add to ~/.config/fish/completions/wican.fish)
register-python-argcomplete --shell fish wican | source
```

## Local development

Prerequisites: Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/philipkocanda/wican-cli.git
cd wican-cli

# Install dependencies (including dev extras)
uv sync --extra dev

# Run the CLI locally
uv run wican --help

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Lint and format
uv run ruff check .
uv run ruff format .
```

## What is WiCAN?

[WiCAN Pro](https://github.com/meatpiHQ/wican-fw) is an ESP32-based WiFi/BLE OBD-II adapter that supports multiple protocols (AutoPID, SLCAN, ELM327, SavvyCAN, RealDash). It can publish vehicle data via MQTT to Home Assistant, log to SD card, and provide a WebSocket terminal interface.

This CLI tool manages the device itself — it does not send CAN/OBD requests to the vehicle. For that, use tools like [python-can](https://github.com/hardbyte/python-can), [SavvyCAN](https://github.com/collin80/SavvyCAN), or [Torque](https://torque-bhp.com/).

## License

Public domain — see [LICENSE](LICENSE) (Unlicense).
