# 3D‑Printer‑Launcher

### [Friendly coffee donation here](https://www.paypal.com/donate/?hosted_button_id=R3DFLDWT2PFC4)

<img width="1314" height="751" alt="{56F2392A-F4FB-4848-AA1E-2DFB0C938970}" src="https://github.com/user-attachments/assets/7c754947-c6b3-4b80-91bf-7af26788301f" />

<img width="1014" height="651" alt="{DA949606-A2CB-435C-BF8C-0D1F7CAD39E2}" src="https://github.com/user-attachments/assets/33d097ca-4289-4d00-88c3-61ed2024ff70" />

<img width="1009" height="763" alt="{627EC487-3B61-44B9-9FEB-AF2AFF46B02A}" src="https://github.com/user-attachments/assets/7a16914d-b442-486f-b916-08666e109e2f" />

If you want to change which sensors are shown or set up a new dashboard for a
different printer, see the setup guide at the repo root:
[`SETUP_NEW_PRINTER.md`](SETUP_NEW_PRINTER.md:1).

Small Windows launcher for my 3D‑printer helper tools:

- Qidi temperature dashboard (Flask web UI)
- Voron/Generic Klipper temperature dashboard (Flask web UI)
- Qidi `webcamd` SSH restart helper

The launcher is a single windowed app (PySide6/Qt) that starts each tool in its
own Python virtual environment, shows live log output, and gives quick access
to log files and project folders. The list of printers/tools and their
Moonraker settings is now fully configurable from the UI.

End‑users are expected to download the pre‑built `.exe` from this repository’s
GitHub Releases page. Building the executable from source is optional and is
documented separately in [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1).


## 1. Repository layout (for reference)

The important pieces for day‑to‑day use are:

- The launcher GUI entry point: [`main.py`](main.py:1)
- Tool configuration model and JSON loader: [`config.ToolEntry`](config.py:13),
  [`config.load_tools_config()`](config.py:68)
- Main window UI: [`main_window.MainWindow()`](main_window.py:28)
- Per‑tool runner widget: [`runner_widget.AppRunner()`](runner_widget.py:21)
- Tools/printers management dialog:
  [`manage_tools_dialog.ManageToolsDialog()`](manage_tools_dialog.py:28)
- Shared styling: [`styles.py`](styles.py:1)
- Qidi temperature dashboard: [`qidi-temps/app.py`](qidi-temps/app.py:1)
- Voron/Klipper temperature dashboard: [`VoronTemps/app.py`](VoronTemps/app.py:1)
- Qidi `webcamd` restart helper:
  [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py:1)

Each temperature dashboard also has its own more detailed README with
background and older one‑off usage instructions:

- [`qidi-temps/README.md`](qidi-temps/README.md:1)
- [`VoronTemps/README.md`](VoronTemps/README.md:1)

The launcher itself is implemented by
[`main_window.MainWindow()`](main_window.py:28) and
[`runner_widget.AppRunner()`](runner_widget.py:21), with some path/packaging
helpers in [`app_spec.py`](app_spec.py:1).


## 2. Downloading and running the launcher (end‑user)

1. Go to this repository’s **Releases** page on GitHub and download the latest
   Windows executable (`.exe`).
2. If you cloned the repo or downloaded the full source ZIP from GitHub, the
   `.exe` should live alongside the `qidi-temps/`, `VoronTemps/` and
   `qidiwebcamdrestart/` folders – you do not need to move anything. If you move
   the `.exe` somewhere else, keep it next to those three folders so the
   launcher can locate the tools.
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
[`AppSpec.venv_python`](app_spec.py:68), so you do **not** need to manually
activate it when starting tools through the UI.


## 4. Configuring printers and Moonraker (UI‑based)

All Klipper printers are accessed via the Moonraker HTTP API. You configure
*which* printers exist and how to contact each one entirely from the launcher
UI.

1. Start the 3D‑Printer‑Launcher.
2. Click **Manage printers** in the top bar, or use the menu:
   **Tools → Manage printers / tools**. This opens
   [`manage_tools_dialog.ManageToolsDialog()`](manage_tools_dialog.py:28).
3. In the left list select an existing printer/tool or click **Add** to create
   a new one.
4. On the right, configure:
   - **Label** – how the card appears in the main window (e.g. `Voron 2.4`,
     `Qidi X‑Plus`).
   - **Project dir** – the folder containing the backend script (typically
     `VoronTemps` or `qidi-temps`).
   - **Script** – entrypoint script file (e.g. `app.py`).
   - **Moonraker IP/host** – just the hostname or IP of the printer running
     Moonraker (e.g. `192.168.1.226`).
   - **Moonraker API port** – TCP port where Moonraker listens (default `7125`).
   - **Dashboard port** – local Flask UI port (e.g. `5000`, `5001`, `5002`);
     use a different value per printer if you want multiple dashboards at the
     same time.
   - **Kind** – `normal` for regular tools, `oneshot` for one‑shot helpers
     (this hides the Stop button and shows a single Run action).
   - **Webcam password** – only relevant for the Qidi Webcam restart tool; this
     writes a local `qidiwebcamdrestart/credentials.json` file ignored by Git.
5. Click **Save changes**. The main window updates immediately to reflect your
   changes.

Under the hood, these settings are stored in `tools_config.json` and mapped to
[`config.ToolEntry`](config.py:13) objects. The Moonraker IP/host and API port
are combined into the full
`http://<host>:<api_port>/printer/objects/query` URL which is passed into the
backend scripts via the `MOONRAKER_API_URL` environment variable.

Most users never need to touch the Python code to change printers – use the
Manage dialog instead. If you want to customise sensors or the HTML overlays
themselves, see [`SETUP_NEW_PRINTER.md`](SETUP_NEW_PRINTER.md:1).


## 5. Using the launcher UI

The main window is implemented by
[`main_window.MainWindow()`](main_window.py:28), which creates one
[`runner_widget.AppRunner()`](runner_widget.py:21) card per tool defined in
`tools_config.json`.

Each card shows:

- Tool name (e.g. “Qidi Temps”, “Voron Temps”, your custom labels)
- Status badge: **Stopped**, **Running**, **Error**, etc.
- Buttons:
  - **Start / Run** – launches the script in the shared `venv` using
    [`QProcess`](runner_widget.py:29)
  - **Stop** – sends a polite terminate, then a kill if needed
  - **Open log** – opens the latest log file created via
    [`AppSpec.log_path`](app_spec.py:82)
  - **Open folder** – opens the underlying project directory in your file
    manager

The top bar provides:

- **Start all / Stop all** – bulk control over all tools at once; the buttons
  enable/disable themselves based on whether any tools are running.
- **Open all logs** – opens each tool’s log file
- **Clear log** – clears the live log pane
- **☀ / 🌙** – switches between light and dark themes (see
  [`MainWindow.set_theme()`](main_window.py:182))

The right‑hand pane shows merged live output from all running tools. Each line
is prefixed with the tool name by
[`MainWindow.append_log()`](main_window.py:196). Long lines automatically wrap
within the log view so they never run off the side of the window.


## 6. Integrating with OBS Studio (displaying temps)

The dashboards are designed to be embedded directly into OBS via **Browser
Source** elements. You can add one source per printer.

By default the launcher uses these local dashboard ports (which you can change
per printer in the Manage dialog):

- Qidi temps: `http://127.0.0.1:5001/`
- Voron/Klipper temps (first printer): `http://127.0.0.1:5000/`
- Additional printers: whatever **Dashboard port** you configured.

### 6.1 Qidi temperature overlay

1. Ensure the shared `venv` is set up (see section 3) and the launcher is
   running.
2. In the launcher, press **Start** on your **Qidi Temps** card. Wait until the
   status shows **Running**.
3. Open a normal browser and verify that `http://127.0.0.1:5001/` (or your
   configured Dashboard port) shows the Qidi dashboard.
4. In **OBS Studio**:
   1. Add (or select) a Scene.
   2. Click **+** in the **Sources** panel → **Browser**.
   3. Give it a name like `QidiTemps`.
   4. Untick **Local file**.
   5. Set **URL** to your local Qidi dashboard URL.
   6. Set **Width/Height** to match your canvas or desired overlay size
      (e.g. 1920×200 for a thin bar at the bottom).
   7. Optionally set **Custom CSS** to adjust background transparency or font.
5. Position and crop the Browser source in your scene as desired.

### 6.2 Voron / Klipper temperature overlay

1. With the launcher and `venv` ready, press **Start** on your Voron/Klipper
   card.
2. Verify in a browser that `http://127.0.0.1:<dashboard-port>/` shows the
   dashboard.
3. In **OBS Studio** repeat the Browser Source steps above, but set the **URL**
   to the appropriate local dashboard port and name the source something like
   `VoronTridentTemps`.

You can run multiple dashboards at the same time and add one Browser source per
printer in OBS.


## 7. Autostart

If you want the launcher to start automatically with Windows:

1. Press **Win + R** and run `shell:startup`.
2. Place a shortcut to the launcher `.exe` into this Startup folder.

Windows will then start the launcher whenever you log in; from there you can
quickly start whichever tools you need.


## 8. Building the executable yourself

Most users should only ever need the pre‑built `.exe` from GitHub Releases.

If you want to build or modify the launcher from source (for example to tweak
styling in [`styles.py`](styles.py:1) or change which tools are launched by
default in `tools_config.json`), see the full developer guide in
[`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1). That document covers the
Nuitka build setup (via [`build_nuitka.py`](build_nuitka.py:1) or
[`build_nuitka.cmd`](build_nuitka.cmd:1)) and the expected folder layout for
releasing your own executables.

