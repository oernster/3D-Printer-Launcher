# 3D‑Printer‑Launcher



<img width="981" height="496" alt="{BF06C511-7CFE-45A9-8B3C-77004C37CC3C}" src="https://github.com/user-attachments/assets/13d7a582-f101-4b4d-84a4-423b2c7ae905" />

<img width="1014" height="651" alt="{DA949606-A2CB-435C-BF8C-0D1F7CAD39E2}" src="https://github.com/user-attachments/assets/33d097ca-4289-4d00-88c3-61ed2024ff70" />

<img width="1009" height="763" alt="{627EC487-3B61-44B9-9FEB-AF2AFF46B02A}" src="https://github.com/user-attachments/assets/7a16914d-b442-486f-b916-08666e109e2f" />

If you want to change which sensors are shown or set up a new dashboard for a
different printer, see the setup guide at the repo root:
[`SETUP_NEW_PRINTER.md`](SETUP_NEW_PRINTER.md:1).

Small Windows launcher for my 3D‑printer helper tools:

- Qidi temperature dashboard (Flask web UI)
- Voron/Klipper temperature dashboard (Flask web UI)
- Qidi `webcamd` SSH restart helper

The launcher is a single windowed app (PySide6/Qt) that starts each tool in its
own Python virtual environment, shows live log output, and gives quick access
to log files and project folders.

End‑users are expected to download the pre‑built `.exe` from this repository’s
GitHub Releases page. Building the executable from source is optional and is
documented separately in [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1).


## 1. Repository layout (for reference)

The important pieces for day‑to‑day use are:

- The launcher GUI: [`main.py`](main.py:1)
- Shared virtualenv requirements: [`requirements.txt`](requirements.txt:1)
- Qidi temperature dashboard: [`qidi-temps/app.py`](qidi-temps/app.py:1)
- Voron/Klipper temperature dashboard: [`VoronTemps/app.py`](VoronTemps/app.py:1)
- Qidi `webcamd` restart helper: [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py:1)

Each temperature dashboard also has its own more detailed README with
background and older one‑off usage instructions:

- [`qidi-temps/README.md`](qidi-temps/README.md:1)
- [`VoronTemps/README.md`](VoronTemps/README.md:1)

The launcher itself is implemented by [`main_window.MainWindow()`](main_window.py:26)
and [`runner_widget.AppRunner()`](runner_widget.py:21), with some path/packaging
helpers in [`app_spec.py`](app_spec.py:1).


## 2. Downloading and running the launcher (end‑user)

1. Go to this repository’s **Releases** page on GitHub and download the latest
   Windows executable (`.exe`).
2. If you cloned the repo or downloaded the full source ZIP from GitHub, the
   `.exe` will already live alongside the `qidi-temps/`, `VoronTemps/` and
   `qidiwebcamdrestart/` folders – you do not need to move anything.
   If you move the `.exe` somewhere else, keep it next to those three folders so
   the launcher can locate the tools.
3. Double‑click the `.exe` to start the **3D‑Printer‑Launcher** window.

The launcher expects a shared Python virtual environment called `venv` to live
next to these folders. If you only downloaded the `.exe` from Releases and not
the full repository, you still need to create this `venv` once as described
below.


## 3. One‑time Python environment setup (Windows)

1. Install Python 3.11+ from https://www.python.org/ and ensure “Add to PATH”
   is enabled during installation.
2. Open **PowerShell** in the folder that contains the launcher `.exe`,
   [`requirements.txt`](requirements.txt:1) and the three project folders.
3. Create a virtual environment (this will create a `venv/` folder):

   ```powershell
   python -m venv venv
   ```

4. Activate the environment and install dependencies:

   ```powershell
   .\venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

The launcher uses this environment automatically via
[`AppSpec.venv_python`](app_spec.py:66), so you do **not** need to manually
activate it when starting tools through the UI.


## 4. Configuring the temperature dashboards

Both dashboards query your printers via the Moonraker HTTP API. You **must**
configure the correct IP/URL once before using them.

If you want to customise which sensors are shown, add new sensors, or set up a
new dashboard folder for another printer, see
[`SETUP_NEW_PRINTER.md`](SETUP_NEW_PRINTER.md:1) for detailed Python and
HTML/JavaScript examples.

### 4.1 Qidi temps (Klipper / Moonraker)

Code: [`qidi-temps/app.py`](qidi-temps/app.py:1)

The Qidi dashboard reads the Moonraker URL from the `MOONRAKER_API_URL`
environment variable, with a fallback hard‑coded default.

The simplest and safest approach is to set `MOONRAKER_API_URL` in the
environment before you start the launcher, for example:

```powershell
$env:MOONRAKER_API_URL = "http://192.168.1.120:7125/printer/objects/query"
```

Alternatively, you can edit the default URL inside
[`qidi-temps/app.py`](qidi-temps/app.py:176) directly.

By default the Qidi dashboard runs on:

- **URL:** `http://127.0.0.1:5001/`

### 4.2 Voron / generic Klipper temps

Code: [`VoronTemps/app.py`](VoronTemps/app.py:1)

This script has the Moonraker API URL hard‑coded near the bottom in the
`MOONRAKER_API_URL` assignment (around
[`VoronTemps/app.py`](VoronTemps/app.py:145)). Edit that line to point at your
Voron/Klipper printer, for example:

```python
MOONRAKER_API_URL = "http://192.168.1.226:7125/printer/objects/query"
```

By default the Voron dashboard runs on:

- **URL:** `http://127.0.0.1:5000/`

After configuring each script, you can either run it via the launcher UI or
manually from the `venv` for testing, for example:

```powershell
.\venv\Scripts\python.exe .\qidi-temps\app.py
.\venv\Scripts\python.exe .\VoronTemps\app.py
```


## 5. Using the launcher UI

The main window is implemented by
[`main_window.MainWindow()`](main_window.py:26), which creates one
[`runner_widget.AppRunner()`](runner_widget.py:21) card per tool defined in
[`main.build_specs()`](main.py:13).

Each card shows:

- Tool name (e.g. “Qidi Temps”, “Voron Temps”)
- Status badge: **Stopped**, **Running**, **Error**, etc.
- Buttons:
  - **Start** – launches the script in the shared `venv` using
    [`QProcess`](runner_widget.py:29)
  - **Stop** – sends a polite terminate, then a kill if needed
  - **Open log** – opens the latest log file created via
    [`AppSpec.log_path`](app_spec.py:79)
  - **Open folder** – opens the underlying project directory in your file
    manager

The top bar also provides:

- **Start all / Stop all** – bulk control over all tools at once
- **Open all logs** – opens each tool’s log file
- **Clear log** – clears the live log pane
- **☀ / 🌙** – switches between light and dark themes (see
  [`MainWindow.set_theme()`](main_window.py:176))

The right‑hand pane shows merged live output from all running tools. Each line
is prefixed with the tool name by
[`MainWindow.append_log()`](main_window.py:190).


## 6. Integrating with OBS Studio (displaying temps)

The dashboards are designed to be embedded directly into OBS via **Browser
Source** elements. You can add one source per printer.

### 6.1 Qidi temperature overlay

1. Ensure the shared `venv` is set up (see section 3) and the launcher is
   running.
2. In the launcher, press **Start** on **Qidi Temps**. Wait until the status
   shows **Running**.
3. Open a normal browser and verify that
   `http://127.0.0.1:5001/` shows the Qidi dashboard.
4. In **OBS Studio**:
   1. Add (or select) a Scene.
   2. Click **+** in the **Sources** panel → **Browser**.
   3. Give it a name like `QidiTemps`.
   4. Untick **Local file**.
   5. Set **URL** to `http://127.0.0.1:5001/`.
   6. Set **Width/Height** to match your canvas or desired overlay size
      (e.g. 1920×200 for a thin bar at the bottom).
   7. Optionally set **Custom CSS** to adjust background transparency or font.
5. Position and crop the Browser source in your scene as desired.

### 6.2 Voron / Klipper temperature overlay

1. With the launcher and `venv` ready, press **Start** on **Voron Temps**.
2. Verify in a browser that `http://127.0.0.1:5000/` shows the Voron
   dashboard.
3. In **OBS Studio** repeat the Browser Source steps above, but set the **URL**
   to `http://127.0.0.1:5000/` and name the source something like
   `VoronTridentTemps`.

You can run both dashboards at the same time and add two Browser sources in
OBS, one per printer.


## 7. Autostart

If you want the launcher to start automatically with Windows:

1. Press **Win + R** and run `shell:startup`.
2. Place a shortcut to the launcher `.exe` into this Startup folder.

Windows will then start the launcher whenever you log in; from there you can
quickly start whichever tools you need.


## 8. Building the executable yourself

Most users should only ever need the pre‑built `.exe` from GitHub Releases.

If you want to build or modify the launcher from source (for example to tweak
styling in [`styles.py`](styles.py:1) or change which tools are launched in
[`main.build_specs()`](main.py:13)), see the full developer guide in
[`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1). That document covers the
Nuitka build setup (via [`build_nuitka.py`](build_nuitka.py:1) or
[`build_nuitka.cmd`](build_nuitka.cmd:1)) and the expected folder layout for
releasing your own executables.
