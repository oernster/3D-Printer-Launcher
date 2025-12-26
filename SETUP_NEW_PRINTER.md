# Setting up a new printer / customising sensors, overlays, and Qidi helpers

This document explains how to adapt the dashboards for a **different printer**
or add/remove sensors in both the **Python backends** and the
**HTML/JavaScript overlays**. It also covers the Qidi webcam restart helper
credentials.

It applies to:

- Qidi temps: [`qidi-temps/app.py`](qidi-temps/app.py) and
  [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html)
- Voron / Klipper temps: [`VoronTemps/app.py`](VoronTemps/app.py) and
  [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html)
- Qidi webcam restart helper: [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py)

My own Voron config repo is public at
https://github.com/oernster/VT350, but the patterns below work regardless of
where your printer configs live.


## 0. Quick start (non‑programmers): add a new printer card (no code)

If you just want the launcher to talk to another printer, you usually **do not**
need to edit any Python or HTML.

1. Open the launcher.
2. Click **Manage printers / tools**.
3. Click **Add**.
4. Set:
   - **Label** (any name you like)
   - **Project dir**: choose the dashboard you want:
     - `VoronTemps` for Klipper/Moonraker printers
     - `qidi-temps` for Qidi temps
   - **Script**: `app.py`
   - **Moonraker IP/host**: the printer’s IP address (example: `192.168.1.226`)
   - **Moonraker API port**: usually `7125`
   - **Dashboard port**: pick a free local port like `5002` (must be unique per card)
5. Click **Save changes**.
6. Back in the main window, press **Start** on your new card.

If the dashboard loads but shows missing/blank sensors, continue to section 2
(Qidi) or section 3 (Voron/Klipper) to customise what is displayed.


## 1. How the data flows

All dashboards follow the same pattern:

1. Python (Flask) talks to Moonraker via HTTP and prepares a JSON payload.
2. That payload is returned from `/temperatures`, `/progress` (and `/fan` on
   Voron) endpoints.
3. The HTML/JS overlay (`index.html`) fetches those endpoints with `fetch()`
   and updates the DOM.

The dashboard web pages themselves are served locally by a production WSGI
server (Waitress) rather than Flask’s development server.

When you add or rename a sensor, you must keep **Python JSON keys** and
**JavaScript lookups** in sync.


## 1.1 How to find the *correct* sensor names (beginner-friendly)

The most common reason a dashboard shows blanks is: the code is asking Moonraker
for a sensor name that your printer doesn’t have.

You have two easy ways to discover the right names:

### Option A (recommended): look in your Klipper UI (Mainsail/Fluidd)

1. Open Mainsail/Fluidd.
2. Go to the **Temperature** section.
3. Note the names shown (for example: `extruder`, `heater_bed`, `chamber`, etc.).
4. For any “extra” sensors you want (like Raspberry Pi temperature, enclosure,
   electronics bay), note the exact label/name that appears.

### Option B: ask Moonraker directly (copy/paste into a browser)

If your Moonraker is reachable on your network, open this in a browser:

- `http://<your-printer-ip>:7125/printer/objects/list`

This returns a big list of all object names Moonraker knows about. You can then
use those exact object names in the dashboard configuration.

If you’re not sure which objects are “temperatures”: look for names starting
with `temperature_sensor`, `heater_`, `extruder`, `temperature_fan`, etc.


## 2. Qidi temps – configuring sensors

Backend: `qidi-temps/app.PrinterDataService` in [`qidi-temps/app.py`](qidi-temps/app.py)

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

Frontend: [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html)

```javascript
this.temperatureElements = {
  'extruder': document.getElementById('extruderTemp'),
  'heater_bed': document.getElementById('bedTemp'),
  'heater_generic chamber': document.getElementById('chamberTemp'),
};
```

The keys in `temperatureElements` **must match** the JSON keys from Python.

### Removing sensors you don’t have (Qidi)

If you don’t have a sensor listed in `self.temperature_sensors`, just delete
that line from the list in [`qidi-temps/app.py`](qidi-temps/app.py). For example,
if you do not have a chamber sensor, remove the `heater_generic chamber` entry.

### Adding a new sensor (Qidi example)

Say your Qidi has a `heater_generic enclosure` sensor you want to show.

1. **Python – add the sensor config** in
   `PrinterDataService.__init__` in [`qidi-temps/app.py`](qidi-temps/app.py):

   ```python
   self.temperature_sensors.append(
       SensorConfig("heater_generic enclosure", ["temperature"], "Enclosure")
   )
   ```

2. **HTML – add a new card** in
   [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html):

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

## 3.0 How to set up *your* Klipper printer from *your* `printer.cfg` (step‑by‑step)

If you are new to Klipper: you do **not** need to guess sensor names.
Everything the dashboard can show comes from your Klipper configuration.

### Step 1 — Open your `printer.cfg`

Open your Klipper config in Mainsail/Fluidd (or via SSH) and locate the
`printer.cfg` file.

### Step 2 — Find the temperature-related sections

Use search (Ctrl+F) for these section headers:

- `\n[temperature_sensor` (custom sensors you define)
- `\n[heater_generic` (generic heaters like chamber)
- `\n[temperature_fan` (fans that report temperature)

Examples of what you might see:

```ini
[temperature_sensor Chamber]
sensor_type: Generic 3950
sensor_pin: ...

[heater_generic chamber]
heater_pin: ...
sensor_type: Generic 3950
sensor_pin: ...

[temperature_fan MCU_Fans]
pin: ...
sensor_type: temperature_mcu
```

### Step 3 — Convert those sections into dashboard “sensor names”

The dashboard pulls data through Moonraker, and Moonraker uses specific object
names.

1. **`[temperature_sensor NAME]`**
   - Moonraker object name becomes: `temperature_sensor NAME`
   - In this repo’s Voron dashboard, you add **only the `NAME` part** into the
     Python list `temperature_sensor_variables`.
   - Example: if your config contains `[temperature_sensor Chamber]`, add
     `"Chamber"` to `temperature_sensor_variables` in
     [`VoronTemps/app.py`](VoronTemps/app.py).

2. **`[heater_generic NAME]`**
   - Moonraker object name becomes: `heater_generic NAME`
   - If you want to show this in the Voron dashboard, add the full object name
     string (including the `heater_generic ` prefix) to the `temperature_sensors`
     dict in [`VoronTemps/app.py`](VoronTemps/app.py).
   - Example: `[heater_generic chamber]` → add
     `"heater_generic chamber": ["temperature", "target"]` (or `"temperature"` only).

3. **`[temperature_fan NAME]`**
   - Moonraker object name becomes: `temperature_fan NAME`
   - Add that full string to `temperature_sensors` if you want to show it.
   - Example: `[temperature_fan MCU_Fans]` → `"temperature_fan MCU_Fans": ["temperature"]`

### Step 4 — Decide what you actually want to display

Most people start with:

- `extruder` and `heater_bed` (almost every Klipper printer has these)
- optionally one chamber/enclosure temperature (if you have it)

Everything else (electronics bay, Pi, toolhead board, etc.) is optional.

### Step 5 — Update the dashboard code (Python + HTML)

The Voron dashboard has **two places** you may need to update:

1. **Python backend** (what data is requested):
   - Edit `temperature_sensors` and/or `temperature_sensor_variables` in
     [`VoronTemps/app.py`](VoronTemps/app.py).

2. **HTML/JS overlay** (what is drawn on screen):
   - Add/remove the matching visual blocks and the JavaScript mapping in
     [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html).

If you only change Python but not the HTML, the new value may be available in
`/temperatures` but won’t appear on the overlay until you add an element for it.

Backend: `VoronTemps/app.PrinterDataFetcher` in [`VoronTemps/app.py`](VoronTemps/app.py)

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
([`VoronTemps/app.py`](VoronTemps/app.py)):

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

Frontend: [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html)

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

### Important note for newcomers (Voron/Klipper)

The names `Internals`, `NucBox`, `NH36`, `Cartographer` are **my personal
examples**. Your printer probably does not have these.

If you leave names in this list that don’t exist on your printer, the dashboard
won’t break, but those sensors will show as `N/A` (or appear blank).

### Simplest safe setup (Voron/Klipper)

If you want a minimal dashboard that works for most Klipper printers:

1. Keep only this in `temperature_sensors`:
   - `extruder`
   - `heater_bed`
2. Remove `temperature_fan MCU_Fans` unless you *know* you have a
   `temperature_fan` object with that exact name.
3. Empty `temperature_sensor_variables` unless you have custom
   `[temperature_sensor ...]` sections in your `printer.cfg`.

That gives you a reliable “Extruder + Bed” overlay.

### If you want extra sensors (Voron/Klipper)

You can add extra temperatures in two different ways:

1. **Standard Moonraker objects** (edit `temperature_sensors`)
   - Examples you might have: `temperature_fan`, `heater_generic`, etc.
   - Use the exact object names you found in section 1.1.

2. **Your own Klipper temperature sensors** (edit `temperature_sensor_variables`)
   - These come from your `printer.cfg` sections like:
     `[temperature_sensor Chamber]`
   - In this case, add just the name part (example: `Chamber`) to the list.

After adding a sensor in Python, you must also add a matching HTML element and
JS mapping in [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html)
so it actually appears on screen.

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
   [`VoronTemps/app.py`](VoronTemps/app.py):

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
   [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html):

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
  `PrinterDataService.get_progress()` in [`qidi-temps/app.py`](qidi-temps/app.py)
- Voron backend:
  `PrinterDataFetcher.fetch_progress_data()` in [`VoronTemps/app.py`](VoronTemps/app.py)

The frontends consume this via:

- Qidi: `DashboardDataManager.getProgress()` and
   `DashboardUIManager.updateProgress()` in
  [`qidi-temps/templates/index.html`](qidi-temps/templates/index.html).
- Voron: `DashboardDataManager.getProgress()` and
   `DashboardUIManager.updateProgress()` in
  [`VoronTemps/templates/index.html`](VoronTemps/templates/index.html).

On Voron there is an additional `/fan` endpoint exposed by
`PrinterDataFetcher.fetch_fan_data()` in [`VoronTemps/app.py`](VoronTemps/app.py) and consumed by
`DashboardUIManager.updateFanSpeed()` in
[`VoronTemps/templates/index.html`](VoronTemps/templates/index.html). To
show more fans, you would extend both the Python payload and the JS UI in the
same pattern as with temperatures.


## 5. Qidi webcam restart credentials

The Qidi webcam restart helper connects to your printer over SSH. To avoid
committing passwords to Git, credentials are loaded from a small JSON file
that is **ignored by version control**.

1. In the `qidiwebcamdrestart/` folder, create a file
   `credentials.json` (this path is already listed in
   [`.gitignore`](.gitignore)).

   Minimum structure:

   ```json
   {
     "password": "makerbase"
   }
   ```

2. Adjust the IP/username in
   [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py)
   if needed:

   ```python
   ip_address = "192.168.1.120"
   username = "root"
   password = _load_password()
   ```

   The helper will fail with a clear error if `credentials.json` is
   missing or malformed, and no password is ever stored in the repo.


## 6. Creating a new dashboard folder for another printer (optional)

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

With the latest launcher, you normally do **not** need to create additional
dashboard folders just to add another Klipper printer. Instead you can:

1. Reuse the existing `VoronTemps/` backend and HTML.
2. Open the launcher and use **Manage printers / tools** to add a new entry
    pointing at `VoronTemps/app.py` with a different label, Moonraker host, API
    port and dashboard port.

### Notes / common pitfalls

- The overlay URLs you put into your browser/OBS are **HTTP**, e.g.
  `http://127.0.0.1:5001/` (not `https://`).
- If a dashboard shows “live” values even after you press Stop in the launcher,
  it means a process is still bound to that local port.

Only create a new dashboard folder when the HTML or the set of sensors for a
printer is fundamentally different from the existing dashboards (for example if
you want a completely different overlay layout for a non‑Voron printer).


