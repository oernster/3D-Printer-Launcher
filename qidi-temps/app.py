"""Qidi temperature dashboard, launched as its own process.

Shares the Moonraker transport with the other bundled tools so the query,
the response parsing and the failure handling have one implementation.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template
from waitress import serve

# This tool runs as its own process with its own directory as sys.path[0], so
# the launcher root has to be added before the shared modules are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moonraker import URL_ENV_VAR, display_host, resolve_query_url
from moonraker_client import MoonrakerClient, status_of

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TOOL_DIR = Path(__file__).resolve().parent

DEFAULT_PRINTER_LABEL = "Qidi"

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 5001

# Waitress threads. Enough to keep the polling endpoints responsive for a
# single-viewer dashboard without reserving pointless workers.
SERVER_THREADS = 8

LABEL_ENV_VAR = "LAUNCHER_TOOL_LABEL"

# Klipper reports print progress as a 0.0 to 1.0 fraction.
PERCENT_SCALE = 100
PERCENT_DECIMALS = 1

VIRTUAL_SDCARD_FIELDS = [
    "file_path",
    "progress",
    "is_active",
    "file_position",
    "file_size",
]

MISSING_READING = "N/A"


@dataclass(frozen=True)
class SensorConfig:
    """One Klipper object shown on the temperature panel."""

    name: str
    attributes: list[str]
    display_name: str


# The sensors a Qidi running Klipper exposes.
TEMPERATURE_SENSORS: tuple[SensorConfig, ...] = (
    SensorConfig("extruder", ["temperature", "target"], "Extruder"),
    SensorConfig("heater_bed", ["temperature", "target"], "Bed"),
    SensorConfig("heater_generic chamber", ["temperature"], "Chamber"),
)


def _as_percentage(fraction: object) -> float:
    """Convert a Klipper 0.0 to 1.0 fraction to a rounded percentage."""

    if not isinstance(fraction, (int, float)):
        return 0.0
    return round(fraction * PERCENT_SCALE, PERCENT_DECIMALS)


class PrinterDataService:
    """Fetches and shapes the readings the Qidi dashboard displays."""

    def __init__(self, client: MoonrakerClient) -> None:
        self.client = client
        self.sensors_query = {s.name: s.attributes for s in TEMPERATURE_SENSORS}

    async def get_temperatures(self) -> dict[str, Any]:
        """Return every configured temperature reading."""

        data = await self.client.query(self.sensors_query)
        if data is None:
            return {sensor.name: {} for sensor in TEMPERATURE_SENSORS}

        sensors_data = status_of(data)
        return {
            sensor.name: {
                attr: sensors_data.get(sensor.name, {}).get(attr)
                for attr in sensor.attributes
            }
            for sensor in TEMPERATURE_SENSORS
        }

    async def get_progress(self) -> dict[str, Any]:
        """Return the current print job's progress."""

        data = await self.client.query({"virtual_sdcard": VIRTUAL_SDCARD_FIELDS})
        if data is None:
            return {"progress_percentage": 0, "is_active": False}

        sdcard = status_of(data).get("virtual_sdcard", {})
        return {
            "progress_percentage": _as_percentage(sdcard.get("progress")),
            "file_path": sdcard.get("file_path", MISSING_READING),
            "is_active": sdcard.get("is_active", False),
            "file_position": sdcard.get("file_position", 0),
            "file_size": sdcard.get("file_size", 0),
        }


class PrinterDashboardApp:
    """The Flask application serving the Qidi dashboard."""

    def __init__(self, data_service: PrinterDataService, api_url: str) -> None:
        self.app = Flask(__name__)
        self.data_service = data_service

        self.app.config["PRINTER_LABEL"] = (
            os.environ.get(LABEL_ENV_VAR) or DEFAULT_PRINTER_LABEL
        )
        self.app.config["MOONRAKER_URL"] = api_url
        self.app.config["MOONRAKER_HOST"] = display_host(api_url)

        self._register_routes()

        # Support running with the templates beside this file rather than in
        # a templates/ subdirectory.
        if not (TOOL_DIR / "templates").exists():
            self.app.template_folder = "."

    def _register_routes(self) -> None:
        @self.app.route("/temperatures")
        async def get_temperatures():
            return jsonify(await self.data_service.get_temperatures())

        @self.app.route("/progress")
        async def get_progress():
            return jsonify(await self.data_service.get_progress())

        @self.app.route("/")
        def index():
            return render_template("index.html")

    def run(self, host: str = DEFAULT_BIND_HOST, port: int = DEFAULT_DASHBOARD_PORT):
        """Serve the dashboard with waitress rather than Flask's dev server."""

        serve(self.app, host=host, port=port, threads=SERVER_THREADS)


def create_app(api_url: str) -> PrinterDashboardApp:
    """Build the dashboard application for the given Moonraker URL."""

    return PrinterDashboardApp(PrinterDataService(MoonrakerClient(api_url)), api_url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qidi printer temperature dashboard")
    parser.add_argument(
        "--moonraker-url",
        dest="moonraker_url",
        help=(
            "Full Moonraker API URL. When omitted, the "
            f"{URL_ENV_VAR} environment variable set by the launcher is used, "
            "then config.json in this directory."
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

    dashboard = create_app(moonraker_url)

    if not asyncio.run(dashboard.data_service.client.probe()):
        logger.warning(
            "Moonraker at %s appears unreachable; starting the dashboard anyway",
            moonraker_url,
        )

    dashboard.run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
