from flask import Flask, render_template, jsonify
from waitress import serve
import aiohttp
import asyncio
import logging
import os
import json
from pathlib import Path
from urllib.parse import urlparse
import argparse
import sys

logging.basicConfig(level=logging.INFO)


DEFAULT_MOONRAKER_URL = "http://192.168.1.226:7125/printer/objects/query"


def _load_moonraker_url_from_config() -> str | None:
    """Try to load the Moonraker URL from a local config.json file.

    The file is expected to live alongside this script and contain at least:

        {"moonraker_url": "http://printer-host:7125/printer/objects/query"}

    Any errors simply cause this function to return None.
    """

    cfg_path = Path(__file__).with_name("config.json")
    if not cfg_path.exists():
        return None

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    url = data.get("moonraker_url") or data.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def resolve_moonraker_url(cli_arg: str | None = None) -> str:
    """Determine which Moonraker API URL to use for this dashboard.

    Precedence (first non-empty wins):
    1. Explicit --moonraker-url CLI argument
    2. Environment variable MOONRAKER_API_URL
    3. Local config.json next to this script (moonraker_url/url key)
    4. Built-in DEFAULT_MOONRAKER_URL
    """

    if cli_arg and cli_arg.strip():
        return cli_arg.strip()

    env = os.environ.get("MOONRAKER_API_URL")
    if env and env.strip():
        return env.strip()

    cfg = _load_moonraker_url_from_config()
    if cfg:
        return cfg

    return DEFAULT_MOONRAKER_URL


async def _probe_moonraker(url: str, timeout: float = 5.0) -> bool:
    """Best‑effort connectivity check to the Moonraker API.

    This runs once at startup so that a misconfigured / unreachable printer
    causes the dashboard process to exit immediately instead of happily
    serving an empty UI on a local port. The launcher will then show an error
    and OBS won't see a dashboard on that port.
    """

    payload = {"objects": {}}

    # Moonraker is often served with a self-signed certificate. When using
    # https, we disable SSL verification for this *connectivity probe* only so
    # that a valid-but-self-signed printer is treated as reachable.
    try:
        parsed = urlparse(url)
    except Exception:
        parsed = None

    connector = None
    if parsed is not None and parsed.scheme == "https":
        connector = aiohttp.TCPConnector(ssl=False)

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload, timeout=timeout) as resp:
                # Any 2xx/3xx response is considered "reachable".
                resp.raise_for_status()
                return True
    except asyncio.TimeoutError as exc:
        # Treat pure timeouts as a soft failure: log a warning but allow the
        # dashboard to start so the user still gets a UI (it will simply show
        # missing data until Moonraker responds).
        logging.warning("Moonraker probe timeout for %s: %r – allowing dashboard to start", url, exc)
        return True
    except Exception as exc:
        logging.error("Moonraker probe failed for %s: %r", url, exc)
        return False

class PrinterDataFetcher:
    """Class responsible for fetching data from the 3D printer API."""
    
    def __init__(self, api_url):
        self.api_url = api_url
        # If the configured URL has the wrong scheme (common when users put
        # https:// for a Moonraker instance that is actually http://), we try
        # a one-step scheme fallback on request failures and remember the last
        # working URL.
        self._working_url = api_url

        # Last-known-good values so brief Moonraker hiccups don't blank the UI.
        self._last_temperatures: dict[str, dict] = {}
        self._last_progress: dict[str, object] = {"progress_percentage": 0}
        self._last_fan: dict[str, object] = {"fan_speed": 0}

        self.temperature_sensors = {
            "extruder": ["temperature", "target"],
            "heater_bed": ["temperature", "target"],
            "temperature_fan MCU_Fans": ["temperature"],
        }
        self.temperature_sensor_variables = ["CHAMBER", "Internals", "NucBox", "NH36", "Cartographer"]

    def _swap_scheme(self, url: str) -> str | None:
        try:
            p = urlparse(url)
        except Exception:
            return None
        if p.scheme == "https":
            return p._replace(scheme="http").geturl()
        if p.scheme == "http":
            return p._replace(scheme="https").geturl()
        return None

    def _candidate_urls(self) -> list[str]:
        # Order matters: prefer the last known working URL, then the configured
        # URL, then scheme-swapped variants.
        urls: list[str] = []
        for u in (self._working_url, self.api_url, self._swap_scheme(self._working_url), self._swap_scheme(self.api_url)):
            if isinstance(u, str) and u and u not in urls:
                urls.append(u)
        return urls

    async def _moonraker_post(self, payload: dict) -> dict | None:
        """POST a payload to Moonraker with short timeouts and scheme fallback."""

        tried: list[str] = []
        last_exc: Exception | None = None

        for url in self._candidate_urls():
            tried.append(url)

            try:
                try:
                    parsed = urlparse(url)
                except Exception:
                    parsed = None

                connector = None
                if parsed is not None and parsed.scheme == "https":
                    connector = aiohttp.TCPConnector(ssl=False)

                timeout = aiohttp.ClientTimeout(total=2)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.post(url, json=payload) as response:
                        response.raise_for_status()
                        data = await response.json()

                # Remember the last successful URL so subsequent requests don't
                # pay the retry cost.
                self._working_url = url
                return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                continue

        logging.error(
            "Moonraker request failed (configured=%s, tried=%s): %r",
            self.api_url,
            tried,
            last_exc,
        )
        return None
    
    async def fetch_temperature_data(self):
        """Fetch temperature data from all sensors."""
        temperatures = {}

        try:
            # Fetch standard sensors
            payload_standard = {"objects": self.temperature_sensors}
            data_standard = await self._moonraker_post(payload_standard)
            if not data_standard:
                return self._last_temperatures

            sensors_data = data_standard.get("result", {}).get("status", {})
            for sensor, attributes in self.temperature_sensors.items():
                sensor_data = sensors_data.get(sensor, {})
                display_name = "MCU" if sensor == "temperature_fan MCU_Fans" else sensor.title().replace("_", " ")
                temperatures[display_name] = {attr: sensor_data.get(attr, "N/A") for attr in attributes}

            # Fetch temperature_sensor variables
            payload_variables = {
                "objects": {f"temperature_sensor {sensor}": ["temperature"] for sensor in self.temperature_sensor_variables}
            }
            data_variables = await self._moonraker_post(payload_variables)
            if not data_variables:
                # Keep the standard temps we already have if the variable query
                # fails.
                self._last_temperatures = temperatures or self._last_temperatures
                return self._last_temperatures

            sensor_variables_data = data_variables.get("result", {}).get("status", {})
            for sensor in self.temperature_sensor_variables:
                sensor_key = f"temperature_sensor {sensor}"
                temperature = sensor_variables_data.get(sensor_key, {}).get("temperature", "N/A")
                temperatures[sensor] = {"temperature": temperature, "target": "N/A"}

            self._last_temperatures = temperatures
            return temperatures
        except Exception as e:
            logging.error(f"Error fetching temperature data from Moonraker API: {e}")
            return self._last_temperatures

    async def fetch_progress_data(self):
        """Fetch print job progress data."""
        try:
            payload = {"objects": {"virtual_sdcard": ["file_path", "progress", "is_active", "file_position", "file_size"]}}
            data = await self._moonraker_post(payload)
            if not data:
                return self._last_progress

            logging.debug("API response: %s", data)

            progress_data = data.get("result", {}).get("status", {}).get("virtual_sdcard", {})
            progress = {
                "progress_percentage": round((progress_data.get("progress") or 0) * 100, 1),
                "file_path": progress_data.get("file_path", "N/A"),
                "is_active": progress_data.get("is_active", False),
                "file_position": progress_data.get("file_position", 0),
                "file_size": progress_data.get("file_size", 0)
            }
            self._last_progress = progress
            return progress
        except Exception as e:
            logging.error(f"Error fetching progress data from Moonraker API: {e}")
            return self._last_progress

    async def fetch_fan_data(self):
        """
        Fetch cooling fan speed data. 
        Returns fan speed as a percentage (0-100).
        """
        fan_data = {"fan_speed": 0}
        payload = {"objects": {"fan": ["speed"]}}
        try:
            data = await self._moonraker_post(payload)
            if not data:
                return self._last_fan

            fan_status = data.get("result", {}).get("status", {}).get("fan", {})
            speed_fraction = fan_status.get("speed", 0)
            # Convert 0.0-1.0 to 0-100%
            fan_data["fan_speed"] = round(speed_fraction * 100, 1)
            self._last_fan = fan_data
            return fan_data
        except Exception as e:
            logging.error(f"Error fetching fan data from Moonraker API: {e}")
            return self._last_fan


class PrinterDashboardApp:
    """Class that defines the Flask application for the 3D printer dashboard."""
    
    def __init__(self, api_url):
        self.app = Flask(__name__)
        self.data_fetcher = PrinterDataFetcher(api_url)

        # Expose the launcher label (if provided) so templates can show which
        # printer this dashboard instance belongs to. This is useful when the
        # same script is run multiple times (Voron 1, Voron 2, etc.).
        self.app.config["PRINTER_LABEL"] = os.environ.get("LAUNCHER_TOOL_LABEL") or "Voron"

        # Also expose a friendly Moonraker host:port string so each dashboard
        # instance is clearly tied to its backend printer in OBS.
        try:
            parsed = urlparse(api_url)
            if parsed.hostname:
                host = parsed.hostname
                if parsed.port:
                    host = f"{host}:{parsed.port}"
            else:
                host = api_url
        except Exception:
            host = api_url

        self.app.config["MOONRAKER_URL"] = api_url
        self.app.config["MOONRAKER_HOST"] = host

        self._register_routes()
    
    def _register_routes(self):
        """Register all the Flask routes."""
        
        @self.app.route('/progress')
        async def get_progress():
            progress = await self.data_fetcher.fetch_progress_data()
            return jsonify(progress)
            
        @self.app.route("/temperatures")
        async def get_temperatures():
            temperatures = await self.data_fetcher.fetch_temperature_data()
            return jsonify(temperatures)

        @self.app.route('/fan')
        async def get_fan_speed():
            """Return the current fan speed in percentage."""
            fan_data = await self.data_fetcher.fetch_fan_data()
            return jsonify(fan_data)

        @self.app.route('/')
        async def index():
            # Do not block initial page render on Moonraker I/O.
            # The frontend already polls /temperatures, /fan, /progress.
            temperatures = {}
            fan_data = {"fan_speed": 0}
            label = self.app.config.get("PRINTER_LABEL", "Voron")
            moonraker_host = self.app.config.get("MOONRAKER_HOST", "unknown")
            return render_template(
                'index.html',
                temperatures=temperatures,
                fan_data=fan_data,
                printer_label=label,
                moonraker_host=moonraker_host,
            )
    
    def run(self, host="127.0.0.1", port=5000):
        """Run the Flask application via a production WSGI server (waitress)."""
        # `threads` keeps async view functions responsive enough for this small
        # dashboard and avoids Flask's development server.
        serve(self.app, host=host, port=port, threads=8)


# Main application entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voron / Klipper Moonraker dashboard")
    parser.add_argument(
        "--moonraker-url",
        dest="moonraker_url",
        help=(
            "Full Moonraker API URL, e.g. "
            "http://printer-host:7125/printer/objects/query. "
            "If omitted, MOONRAKER_API_URL env var, config.json, "
            "or a built-in default will be used."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for the Flask server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for the Flask server (default: 5000)",
    )
    # Debug flag intentionally removed/ignored for packaged usage.

    args = parser.parse_args()

    moonraker_url = resolve_moonraker_url(args.moonraker_url)
    logging.info("Using Moonraker API URL: %s", moonraker_url)

    # Only use the probe for logging/diagnostics now; do *not* prevent the
    # dashboard from starting. This avoids any chance that transient network
    # issues or HTTPS quirks stop the local UI from binding to its port.
    try:
        ok = asyncio.run(_probe_moonraker(moonraker_url))
        if not ok:
            logging.warning("Moonraker at %s appears unreachable (probe failed). Dashboard will still start.", moonraker_url)
    except Exception as exc:
        logging.warning("Moonraker probe raised %r – ignoring and starting dashboard anyway.", exc)

    app = PrinterDashboardApp(moonraker_url)
    # Run with a production WSGI server.
    app.run(host=args.host, port=args.port)
