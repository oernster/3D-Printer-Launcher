"""One-shot helper that restarts the webcam daemon on a Qidi printer.

The launcher runs this as its own process and passes the printer's Moonraker
URL in the environment, so the host comes from the user's own configuration
rather than being written into this file.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import paramiko

# This tool runs as its own process with its own directory as sys.path[0], so
# the launcher root has to be added before the shared modules are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moonraker import URL_ENV_VAR, resolve_query_url, split_query_url
from webcam_credentials import (
    CREDENTIALS_FILENAME,
    PASSWORD_ENV_VAR,
    resolve_password,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_DIR = Path(__file__).resolve().parent

# The account Qidi's stock firmware exposes over SSH.
SSH_USERNAME = "root"

# The service command this helper exists to run.
RESTART_COMMAND = "sudo service webcamd restart"

# Seconds to wait for the shell prompt, for the command and before reading.
PROMPT_WAIT_SECONDS = 1.0
COMMAND_WAIT_SECONDS = 1.0
EXIT_WAIT_SECONDS = 0.5

# Bytes of shell output read back and echoed into the launcher log.
OUTPUT_BUFFER_BYTES = 5000


def ssh_command(host: str, username: str, password: str, command: str) -> str:
    """Run one command over SSH and return whatever the shell printed."""

    client = paramiko.SSHClient()
    # The target is the user's own printer on their own LAN, reached by an
    # address they typed in themselves and its firmware regenerates its host
    # key on reflash. Prompting for key approval would break the one-click
    # action this tool exists to provide.
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

    try:
        client.connect(host, username=username, password=password)
        session = client.invoke_shell()

        time.sleep(PROMPT_WAIT_SECONDS)
        session.send(command + "\n")
        time.sleep(COMMAND_WAIT_SECONDS)

        session.send("exit\n")
        time.sleep(EXIT_WAIT_SECONDS)

        return session.recv(OUTPUT_BUFFER_BYTES).decode(errors="replace")
    finally:
        client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restart the webcam daemon on a Qidi printer over SSH"
    )
    parser.add_argument(
        "--host",
        help=(
            "Printer hostname or IP address. When omitted it is taken from "
            f"the {URL_ENV_VAR} environment variable the launcher sets."
        ),
    )
    parser.add_argument(
        "--moonraker-url",
        dest="moonraker_url",
        help="Full Moonraker API URL to take the printer's host from.",
    )
    # Accepted and ignored so the launcher can pass a dashboard port to every
    # tool uniformly. This helper serves nothing.
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    return parser


def resolve_host(args: argparse.Namespace) -> str | None:
    """Work out which printer to connect to."""

    if args.host and args.host.strip():
        return args.host.strip()

    host, _port = split_query_url(resolve_query_url(args.moonraker_url, TOOL_DIR))
    return host


def main() -> int:
    args = build_parser().parse_args()

    host = resolve_host(args)
    if not host:
        logger.error(
            "No printer address configured. Set the printer's host in the "
            "launcher (Manage printers / tools) or pass --host."
        )
        return 1

    password = resolve_password(TOOL_DIR / CREDENTIALS_FILENAME)
    if not password:
        logger.error(
            "No SSH password available. Enter one in the launcher under "
            "Manage printers / tools (which writes %s) or set %s.",
            TOOL_DIR / CREDENTIALS_FILENAME,
            PASSWORD_ENV_VAR,
        )
        return 1

    logger.info("Restarting webcamd on %s", host)
    output = ssh_command(host, SSH_USERNAME, password, RESTART_COMMAND)
    if output.strip():
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
