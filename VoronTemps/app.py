from flask import Flask, render_template, jsonify
import aiohttp
import asyncio
import logging
import os
import json
from pathlib import Path
import argparse

logging.basicConfig(level=logging.DEBUG)


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

class PrinterDataFetcher:
    """Class responsible for fetching data from the 3D printer API."""
    
    def __init__(self, api_url):
        self.api_url = api_url
        self.temperature_sensors = {
            "extruder": ["temperature", "target"],
            "heater_bed": ["temperature", "target"],
            "temperature_fan MCU_Fans": ["temperature"],
        }
        self.temperature_sensor_variables = ["CHAMBER", "Internals", "NucBox", "NH36", "Cartographer"]
    
    async def fetch_temperature_data(self):
        """Fetch temperature data from all sensors."""
        temperatures = {}

        async with aiohttp.ClientSession() as session:
            try:
                # Fetch standard sensors
                payload_standard = {"objects": self.temperature_sensors}
                async with session.post(self.api_url, json=payload_standard) as response:
                    response.raise_for_status()
                    data_standard = await response.json()

                sensors_data = data_standard.get("result", {}).get("status", {})
                for sensor, attributes in self.temperature_sensors.items():
                    sensor_data = sensors_data.get(sensor, {})
                    display_name = "MCU" if sensor == "temperature_fan MCU_Fans" else sensor.title().replace("_", " ")
                    temperatures[display_name] = {attr: sensor_data.get(attr, "N/A") for attr in attributes}

                # Fetch temperature_sensor variables
                payload_variables = {"objects": {f"temperature_sensor {sensor}": ["temperature"] 
                                                for sensor in self.temperature_sensor_variables}}
                async with session.post(self.api_url, json=payload_variables) as response:
                    response.raise_for_status()
                    data_variables = await response.json()

                sensor_variables_data = data_variables.get("result", {}).get("status", {})
                for sensor in self.temperature_sensor_variables:
                    sensor_key = f"temperature_sensor {sensor}"
                    temperature = sensor_variables_data.get(sensor_key, {}).get("temperature", "N/A")
                    temperatures[sensor] = {"temperature": temperature, "target": "N/A"}

            except aiohttp.ClientError as e:
                logging.error(f"Error fetching temperature data from Moonraker API: {e}")

        return temperatures

    async def fetch_progress_data(self):
        """Fetch print job progress data."""
        try:
            payload = {"objects": {"virtual_sdcard": ["file_path", "progress", "is_active", "file_position", "file_size"]}}
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()

            logging.debug("API response: %s", data)

            progress_data = data.get("result", {}).get("status", {}).get("virtual_sdcard", {})
            progress = {
                "progress_percentage": round((progress_data.get("progress") or 0) * 100, 1),
                "file_path": progress_data.get("file_path", "N/A"),
                "is_active": progress_data.get("is_active", False),
                "file_position": progress_data.get("file_position", 0),
                "file_size": progress_data.get("file_size", 0)
            }
            return progress
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching progress data from Moonraker API: {e}")
            return {"progress_percentage": 0}

    async def fetch_fan_data(self):
        """
        Fetch cooling fan speed data. 
        Returns fan speed as a percentage (0-100).
        """
        fan_data = {"fan_speed": 0}
        payload = {"objects": {"fan": ["speed"]}}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.api_url, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    fan_status = data.get("result", {}).get("status", {}).get("fan", {})
                    speed_fraction = fan_status.get("speed", 0)
                    # Convert 0.0-1.0 to 0-100%
                    fan_data["fan_speed"] = round(speed_fraction * 100, 1)
            except aiohttp.ClientError as e:
                logging.error(f"Error fetching fan data from Moonraker API: {e}")

        return fan_data


class PrinterDashboardApp:
    """Class that defines the Flask application for the 3D printer dashboard."""
    
    def __init__(self, api_url):
        self.app = Flask(__name__)
        self.data_fetcher = PrinterDataFetcher(api_url)
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
            # Fetch basic data to display
            temperatures = await self.data_fetcher.fetch_temperature_data()
            fan_data = await self.data_fetcher.fetch_fan_data()
            return render_template('index.html', temperatures=temperatures, fan_data=fan_data)
    
    def run(self, host="127.0.0.1", port=5000, debug=True, use_reloader=False):
        """Run the Flask application."""
        self.app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )

    args = parser.parse_args()

    moonraker_url = resolve_moonraker_url(args.moonraker_url)
    logging.info("Using Moonraker API URL: %s", moonraker_url)

    app = PrinterDashboardApp(moonraker_url)
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
