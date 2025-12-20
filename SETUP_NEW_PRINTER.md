# Setting up a new printer / customising sensors, overlays, and Qidi helpers

This document explains how to adapt the dashboards for a **different printer**
or add/remove sensors in both the **Python backends** and the
**HTML/JavaScript overlays**. It also covers the Qidi webcam restart helper
credentials.

It applies to:

- Qidi temps: [`qidi-temps/app.py`](qidi-temps/app.py:1) and
  [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html:1)
- Voron / Klipper temps: [`VoronTemps/app.py`](VoronTemps/app.py:1) and
  [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html:1)
- Qidi webcam restart helper: [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py:1)

My own Voron config repo is public at
https://github.com/oernster/VT350, but the patterns below work regardless of
where your printer configs live.


## 1. How the data flows

All dashboards follow the same pattern:

1. Python (Flask) talks to Moonraker via HTTP and prepares a JSON payload.
2. That payload is returned from `/temperatures`, `/progress` (and `/fan` on
   Voron) endpoints.
3. The HTML/JS overlay (`index.html`) fetches those endpoints with `fetch()`
   and updates the DOM.

When you add or rename a sensor, you must keep **Python JSON keys** and
**JavaScript lookups** in sync.


## 2. Qidi temps – configuring sensors

Backend: [`qidi-temps/app.PrinterDataService`](qidi-temps/app.py:55)

```python
class PrinterDataService:
    """Service for fetching and processing printer data"""

    def __init__(self, api_client: APIClient):
        self.api_client = api_client

        # Define temperature sensors configuration
        self.temperature_sensors = [
            SensorConfig("extruder", ["temperature", "target"], "Extruder"),
            SensorConfig("heater_bed", ["temperature", "target"], "Bed"),
            SensorConfig("heater_generic chamber", ["temperature"], "Chamber"),
        ]

        # Build the sensors query object
        self.sensors_query = {
            sensor.name: sensor.attributes for sensor in self.temperature_sensors
        }
```

Key points:

- `sensor.name` must match the object name in Moonraker’s
  `printer.objects.query` API, for example:
  - `extruder`
  - `heater_bed`
  - `heater_generic chamber`
- `sensor.attributes` are the fields you want back, typically
  `"temperature"` and optionally `"target"`.
- The JSON returned from `/temperatures` looks like:

  ```json
  {
    "extruder": { "temperature": 205.3, "target": 210.0 },
    "heater_bed": { "temperature": 60.0, "target": 60.0 },
    "heater_generic chamber": { "temperature": 38.7 }
  }
  ```

Frontend: [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html:1)

```javascript
this.temperatureElements = {
  'extruder': document.getElementById('extruderTemp'),
  'heater_bed': document.getElementById('bedTemp'),
  'heater_generic chamber': document.getElementById('chamberTemp'),
};
```

The keys in `temperatureElements` **must match** the JSON keys from Python.

### Adding a new sensor (Qidi example)

Say your Qidi has a `heater_generic enclosure` sensor you want to show.

1. **Python – add the sensor config** in
   [`PrinterDataService.__init__`](qidi-temps/app.py:58):

   ```python
   self.temperature_sensors.append(
       SensorConfig("heater_generic enclosure", ["temperature"], "Enclosure")
   )
   ```

2. **HTML – add a new card** in
   [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html:124):

   ```html
   <div class="sensor">
     <strong>Enclosure</strong>
     <div id="enclosureTemp" style="color: orange;">-- °C</div>
   </div>
   ```

3. **JS – map the JSON key to that element** inside
   `DashboardUIManager`:

   ```javascript
   this.temperatureElements = {
     'extruder': document.getElementById('extruderTemp'),
     'heater_bed': document.getElementById('bedTemp'),
     'heater_generic chamber': document.getElementById('chamberTemp'),
     'heater_generic enclosure': document.getElementById('enclosureTemp'),
   };
   ```

No other changes are needed; the existing `updateTemperatures()` logic will
pick it up.


## 3. Voron / Klipper temps – configuring sensors

Backend: [`VoronTemps/app.PrinterDataFetcher`](VoronTemps/app.py:8)

```python
class PrinterDataFetcher:
    def __init__(self, api_url):
        self.api_url = api_url
        self.temperature_sensors = {
            "extruder": ["temperature", "target"],
            "heater_bed": ["temperature", "target"],
            "temperature_fan MCU_Fans": ["temperature"],
        }
        self.temperature_sensor_variables = [
            "CHAMBER",
            "Internals",
            "NucBox",
            "NH36",
            "Cartographer",
        ]
```

There are **two groups** here:

1. `temperature_sensors` – “standard” Moonraker objects (`extruder`,
   `heater_bed`, `temperature_fan MCU_Fans`, etc.).
2. `temperature_sensor_variables` – names of Klipper `temperature_sensor`
   objects you have defined in your `printer.cfg`, such as `temperature_sensor
   CHAMBER`.

Within `fetch_temperature_data()`
([`VoronTemps/app.py`](VoronTemps/app.py:20)):

```python
for sensor, attributes in self.temperature_sensors.items():
    sensor_data = sensors_data.get(sensor, {})
    display_name = "MCU" if sensor == "temperature_fan MCU_Fans" else sensor.title().replace("_", " ")
    temperatures[display_name] = {attr: sensor_data.get(attr, "N/A") for attr in attributes}

...

for sensor in self.temperature_sensor_variables:
    sensor_key = f"temperature_sensor {sensor}"
    temperature = sensor_variables_data.get(sensor_key, {}).get("temperature", "N/A")
    temperatures[sensor] = {"temperature": temperature, "target": "N/A"}
```

- Standard sensors become JSON keys like `"Extruder"`, `"Heater Bed"`,
  `"MCU"`.
- `temperature_sensor_variables` become keys exactly matching the names in that
  list (e.g. `"CHAMBER"`, `"Internals"`).

Frontend: [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html:1)

```javascript
this.temperatureElements = {
  'Extruder':    document.getElementById('extruder').querySelector('.temp-value'),
  'Heater Bed':  document.getElementById('heaterBed').querySelector('.temp-value'),
  'CHAMBER':     document.getElementById('chamber').querySelector('.temp-value'),
  'MCU':         document.getElementById('mcu').querySelector('.temp-value'),
  'Internals':   document.getElementById('internals').querySelector('.temp-value'),
  'NucBox':      document.getElementById('nucbox').querySelector('.temp-value'),
  'NH36':        document.getElementById('nh36').querySelector('.temp-value'),
  'Cartographer':document.getElementById('cartographer').querySelector('.temp-value'),
};
```

Again, the keys in `temperatureElements` must match the JSON keys from
`fetch_temperature_data()`.

### Adding a new `temperature_sensor` (Voron example)

Assume you define sensors like this in your Klipper `printer.cfg` (for a real
example, see the configs in https://github.com/oernster/VT350):

```ini
[temperature_sensor CHAMBER]
sensor_type: Generic 3950
sensor_pin: ...

[temperature_sensor Internals]
sensor_type: Generic 3950
sensor_pin: ...

[temperature_sensor NucBox]
sensor_type: Generic 3950
sensor_pin: ...

[temperature_sensor NH36]
sensor_type: Generic 3950
sensor_pin: ...

[temperature_sensor Cartographer]
sensor_type: Generic 3950
sensor_pin: ...

; New sensor example
[temperature_sensor Toolhead]
sensor_type: Generic 3950
sensor_pin: ...
```

1. **Python – add `Toolhead` to the variables list** in
   [`VoronTemps/app.py`](VoronTemps/app.py:18):

   ```python
   self.temperature_sensor_variables = [
       "CHAMBER",
       "Internals",
       "NucBox",
       "NH36",
       "Cartographer",
       "Toolhead",  # new
   ]
   ```

   The JSON from `/temperatures` will then include a `"Toolhead"` key.

2. **HTML – add a matching block** in
   [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html:134):

   ```html
   <div id="toolhead" class="sensor">
     Toolhead:
     <span class="temp-value">--</span>
     <span style="color:orange">°C</span>
   </div>
   ```

3. **JS – register the element** in the `DashboardUIManager` mapping:

   ```javascript
   this.temperatureElements = {
     'Extruder':  document.getElementById('extruder').querySelector('.temp-value'),
     // ... existing entries ...
     'Toolhead':  document.getElementById('toolhead').querySelector('.temp-value'),
   };
   ```

The shared `updateTemperatures()` logic will then keep `Toolhead` updated.


## 4. Progress bar and fan data

Both dashboards expose print progress via a `/progress` endpoint and render a
single bar in the HTML.

- Qidi backend:
  [`PrinterDataService.get_progress()`](qidi-temps/app.py:92)
- Voron backend:
  [`PrinterDataFetcher.fetch_progress_data()`](VoronTemps/app.py:56)

The frontends consume this via:

- Qidi: `DashboardDataManager.getProgress()` and
  `DashboardUIManager.updateProgress()` in
  [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html:145).
- Voron: `DashboardDataManager.getProgress()` and
  `DashboardUIManager.updateProgress()` in
  [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html:190).

On Voron there is an additional `/fan` endpoint exposed by
[`PrinterDataFetcher.fetch_fan_data()`](VoronTemps/app.py:80) and consumed by
`DashboardUIManager.updateFanSpeed()` in
[`VoronTemps/templates/index.html`](VoronTemps/templates/index.html:292). To
show more fans, you would extend both the Python payload and the JS UI in the
same pattern as with temperatures.


## 5. Qidi webcam restart credentials

The Qidi webcam restart helper connects to your printer over SSH. To avoid
committing passwords to Git, credentials are loaded from a small JSON file
that is **ignored by version control**.

1. In the `qidiwebcamdrestart/` folder, create a file
   `credentials.json` (this path is already listed in
   [`.gitignore`](.gitignore:1)).

   Minimum structure:

   ```json
   {
     "password": "makerbase"
   }
   ```

2. Adjust the IP/username in
   [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py:35)
   if needed:

   ```python
   ip_address = "192.168.1.120"
   username = "root"
   password = _load_password()
   ```

   The helper will fail with a clear error if `credentials.json` is
   missing or malformed, and no password is ever stored in the repo.


## 6. Creating a new dashboard folder for another printer

If you want a completely separate overlay (e.g. for a second Voron):

1. Copy one of the existing folders, for example:

   ```text
   VoronTemps/        ->  VoronTemps_VT350/
   ```

2. Adjust the backend:
   - Rename the Flask app/module if desired.
   - Update `MOONRAKER_API_URL` or `config.json` / `--moonraker-url` settings
     to point at the new printer.
   - Tweak `temperature_sensors` / `temperature_sensor_variables` (Voron) or
     `temperature_sensors` (Qidi) as described above.

3. Adjust the frontend `index.html`:
   - Change the visible labels to match your new sensors.
   - Ensure the JS key names match the JSON keys from your modified backend.

4. Register the new tool in the launcher using the “Manage printers / tools”
   dialog (or by editing `tools_config.json` directly), pointing `project_dir`
   to your new folder and `script` to your Flask app.

With these steps you can bring up overlays for additional printers while
reusing the same patterns and code structure.

