"""Reads temperatures, print progress and fan speed for the Voron dashboard.

The Moonraker transport itself lives in the shared ``moonraker_client`` module
at the launcher root; this file only knows which objects this printer exposes
and how they are presented.
"""

from __future__ import annotations

import logging

from moonraker_client import MoonrakerClient, status_of

logger = logging.getLogger(__name__)

# Placeholder shown for a sensor Moonraker did not report.
MISSING_READING = "N/A"

# Klipper objects queried for the temperature panel and the attributes wanted
# from each. These mirror the printer's own configuration section names.
TEMPERATURE_SENSORS: dict[str, list[str]] = {
    "extruder": ["temperature", "target"],
    "heater_bed": ["temperature", "target"],
    "temperature_fan MCU_Fans": ["temperature"],
}

# Klipper reports these under "temperature_sensor <name>" and they have a
# reading but no target.
TEMPERATURE_SENSOR_NAMES: list[str] = [
    "CHAMBER",
    "Internals",
    "NucBox",
    "NH36",
    "Cartographer",
]

# The one object name whose title-cased form would read badly in the UI.
MCU_SENSOR_KEY = "temperature_fan MCU_Fans"
MCU_DISPLAY_NAME = "MCU"

VIRTUAL_SDCARD_FIELDS = [
    "file_path",
    "progress",
    "is_active",
    "file_position",
    "file_size",
]

# Klipper reports fan speed and print progress as a 0.0 to 1.0 fraction.
PERCENT_SCALE = 100
PERCENT_DECIMALS = 1


def _display_name(sensor_key: str) -> str:
    """Human-readable panel heading for a Klipper object name."""

    if sensor_key == MCU_SENSOR_KEY:
        return MCU_DISPLAY_NAME
    return sensor_key.title().replace("_", " ")


def _as_percentage(fraction: object) -> float:
    """Convert a Klipper 0.0 to 1.0 fraction to a rounded percentage."""

    if not isinstance(fraction, (int, float)):
        return 0.0
    return round(fraction * PERCENT_SCALE, PERCENT_DECIMALS)


class PrinterDataFetcher:
    """Fetches the readings the dashboard shows, keeping the last good ones.

    Every fetch returns the previous reading when Moonraker does not answer,
    so a brief hiccup leaves the panel showing slightly stale numbers rather
    than blanking it.
    """

    def __init__(self, api_url: str) -> None:
        self.client = MoonrakerClient(api_url)
        self.api_url = api_url

        self._last_temperatures: dict[str, dict] = {}
        self._last_progress: dict[str, object] = {"progress_percentage": 0}
        self._last_fan: dict[str, object] = {"fan_speed": 0}

    async def fetch_temperature_data(self) -> dict[str, dict]:
        """Fetch every configured temperature reading."""

        standard = await self.client.query(TEMPERATURE_SENSORS)
        if standard is None:
            return self._last_temperatures

        sensors_data = status_of(standard)
        temperatures: dict[str, dict] = {}
        for sensor_key, attributes in TEMPERATURE_SENSORS.items():
            sensor_data = sensors_data.get(sensor_key, {})
            temperatures[_display_name(sensor_key)] = {
                attr: sensor_data.get(attr, MISSING_READING) for attr in attributes
            }

        variables = await self.client.query(
            {
                f"temperature_sensor {name}": ["temperature"]
                for name in TEMPERATURE_SENSOR_NAMES
            }
        )
        if variables is None:
            # Keep the standard readings already collected on this pass.
            self._last_temperatures = temperatures or self._last_temperatures
            return self._last_temperatures

        variables_data = status_of(variables)
        for name in TEMPERATURE_SENSOR_NAMES:
            reading = variables_data.get(f"temperature_sensor {name}", {})
            temperatures[name] = {
                "temperature": reading.get("temperature", MISSING_READING),
                "target": MISSING_READING,
            }

        self._last_temperatures = temperatures
        return temperatures

    async def fetch_progress_data(self) -> dict[str, object]:
        """Fetch the current print job's progress."""

        data = await self.client.query({"virtual_sdcard": VIRTUAL_SDCARD_FIELDS})
        if data is None:
            return self._last_progress

        sdcard = status_of(data).get("virtual_sdcard", {})
        progress = {
            "progress_percentage": _as_percentage(sdcard.get("progress")),
            "file_path": sdcard.get("file_path", MISSING_READING),
            "is_active": sdcard.get("is_active", False),
            "file_position": sdcard.get("file_position", 0),
            "file_size": sdcard.get("file_size", 0),
        }
        self._last_progress = progress
        return progress

    async def fetch_fan_data(self) -> dict[str, object]:
        """Fetch the part-cooling fan speed as a percentage."""

        data = await self.client.query({"fan": ["speed"]})
        if data is None:
            return self._last_fan

        fan_status = status_of(data).get("fan", {})
        fan_data = {"fan_speed": _as_percentage(fan_status.get("speed"))}
        self._last_fan = fan_data
        return fan_data
