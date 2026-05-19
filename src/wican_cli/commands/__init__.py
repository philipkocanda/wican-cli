"""WiCAN CLI command modules."""

from wican_cli.commands.autopid import register as register_autopid
from wican_cli.commands.config import register as register_config
from wican_cli.commands.logs import register as register_logs
from wican_cli.commands.protocol import register as register_protocol
from wican_cli.commands.reboot import register as register_reboot
from wican_cli.commands.sleep import register as register_sleep
from wican_cli.commands.status import register as register_status

ALL_REGISTERS = [
    register_config,
    register_sleep,
    register_status,
    register_reboot,
    register_logs,
    register_protocol,
    register_autopid,
]
