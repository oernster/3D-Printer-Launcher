"""Voron / Klipper temperature dashboard, launched as its own process.

The launcher starts this script with the shared virtualenv and passes the
Moonraker URL through the environment, so the address of a printer appears
in exactly one place: the user's own configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template
from waitress import serve

# This tool runs as its own process with its own directory as sys.path[0], so
# the launcher root has to be added before the shared modules are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetcher import PrinterDataFetcher

from moonraker import URL_ENV_VAR, display_host, resolve_query_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_DIR = Path(__file__).resolve().parent

# Shown when the launcher did not pass a label of its own.
DEFAULT_PRINTER_LABEL = "Voron"

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 5000

# Waitress threads. Enough to keep the three polling endpoints responsive for
# a single-viewer dashboard without reserving pointless workers.
SERVER_THREADS = 8

# Environment variable the launcher uses to name the printer in the UI.
LABEL_ENV_VAR = "LAUNCHER_TOOL_LABEL"


class PrinterDashboardApp:
    """The Flask application serving the dashboard for one printer."""

    def __init__(self, api_url: str) -> None:
        self.app = Flask(__name__)
        self.data_fetcher = PrinterDataFetcher(api_url)

        # The same script serves several printers, one process each, so the
        # label and host are exposed to the template to tell them apart.
        self.app.config["PRINTER_LABEL"] = (
            os.environ.get(LABEL_ENV_VAR) or DEFAULT_PRINTER_LABEL
        )
        self.app.config["MOONRAKER_URL"] = api_url
        self.app.config["MOONRAKER_HOST"] = display_host(api_url)

        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.route("/progress")
        async def get_progress():
            return jsonify(await self.data_fetcher.fetch_progress_data())

        @self.app.route("/temperatures")
        async def get_temperatures():
            return jsonify(await self.data_fetcher.fetch_temperature_data())

        @self.app.route("/fan")
        async def get_fan_speed():
            return jsonify(await self.data_fetcher.fetch_fan_data())

        @self.app.route("/")
        async def index():
            # The first render does no Moonraker I/O; the page polls the
            # three endpoints above as soon as it loads.
            return render_template(
                "index.html",
                temperatures={},
                fan_data={"fan_speed": 0},
                printer_label=self.app.config["PRINTER_LABEL"],
                moonraker_host=self.app.config["MOONRAKER_HOST"],
            )

    def run(self, host: str = DEFAULT_BIND_HOST, port: int = DEFAULT_DASHBOARD_PORT):
        """Serve the dashboard with waitress rather than Flask's dev server."""

        serve(self.app, host=host, port=port, threads=SERVER_THREADS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Voron / Klipper Moonraker dashboard")
    parser.add_argument(
        "--moonraker-url",
        dest="moonraker_url",
        help=(
            "Full Moonraker API URL, for example "
            "http://printer-host:7125/printer/objects/query. When omitted, "
            f"the {URL_ENV_VAR} environment variable set by the launcher is "
            "used, then config.json in this directory."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_BIND_HOST,
        help=f"Host interface for the dashboard (default: {DEFAULT_BIND_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Port for the dashboard (default: {DEFAULT_DASHBOARD_PORT})",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    moonraker_url = resolve_query_url(args.moonraker_url, TOOL_DIR)
    if not moonraker_url:
        logger.error(
            "No Moonraker address configured. Set the printer's host in the "
            "launcher (Manage printers / tools) or pass --moonraker-url."
        )
        return 1

    logger.info("Using Moonraker API URL: %s", moonraker_url)

    dashboard = PrinterDashboardApp(moonraker_url)

    # The probe is advisory only. A printer that is asleep or slow must not
    # stop the dashboard binding its port or the launcher reports it dead.
    if not asyncio.run(dashboard.data_fetcher.client.probe()):
        logger.warning(
            "Moonraker at %s appears unreachable; starting the dashboard anyway",
            moonraker_url,
        )

    dashboard.run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
