# 3D‑Printer‑Launcher – Developer Guide

This document is for contributors and power users who want to build or modify
the launcher executable themselves. End‑users can simply download the latest
`.exe` from this repository’s GitHub Releases page and follow
[`README.md`](README.md).


## 1. Project overview

- Launcher entry point: [`main.py`](main.py)
- Version, read from the `VERSION` file: [`version.py`](version.py)
- Tool specification and path handling: [`app_spec.py`](app_spec.py)
- Persistent tool/printer config model: [`config.py`](config.py) (see `ToolEntry`, `load_tools_config()`)
- Main window UI: [`main_window.py`](main_window.py)
- Per‑tool runner widget: [`runner_widget.py`](runner_widget.py)
- Tools/printers management dialog: [`manage_tools_dialog.py`](manage_tools_dialog.py)
- The dialog's per‑entry editor form: [`tool_form.py`](tool_form.py)
- Webcam helper credentials file handling: [`webcam_credentials.py`](webcam_credentials.py)
- Shared styling: [`styles.py`](styles.py)
- Nuitka build helper script: [`build_nuitka.py`](build_nuitka.py)
- Windows build wrapper, delegates to the above: [`build_nuitka.cmd`](build_nuitka.cmd)
- macOS and Linux build script, all distributions: [`build_nuitka_unix.sh`](build_nuitka_unix.sh)

Shared between the launcher and the bundled tools:

- Moonraker URL handling, standard library only:
  [`moonraker.py`](moonraker.py)
- The async Moonraker client, which needs `aiohttp`:
  [`moonraker_client.py`](moonraker_client.py)

The split matters: [`moonraker.py`](moonraker.py) is imported by the launcher,
so keeping `aiohttp` out of it keeps `aiohttp` out of the Nuitka build.

At runtime `config.enabled_specs()` in [`config.py`](config.py) builds the
list of tools from the user's configuration:

- Qidi Temps: [`qidi-temps/app.py`](qidi-temps/app.py)
- Qidi `webcamd` restart: [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py)
- Voron Temps: [`VoronTemps/app.py`](VoronTemps/app.py), with its Moonraker
  reading logic in [`VoronTemps/fetcher.py`](VoronTemps/fetcher.py)

Each bundled tool runs as its own process with its own directory as
`sys.path[0]`, so each one inserts the launcher root into `sys.path` before
importing the shared modules. That is why those files carry an `E402`
exemption in both [`.flake8`](.flake8) and [`pyproject.toml`](pyproject.toml).

The base directory detection and log‑file naming live in
`app_spec._compute_base_dir()` and `AppSpec` in [`app_spec.py`](app_spec.py).


### 1.1 Versioning

`VERSION` at the repository root is the single source of truth. Nothing else
holds a version string:

- [`version.py`](version.py) reads it, falling back to `0.0.0-dev` when the
  file is unreadable.
- [`pyproject.toml`](pyproject.toml) declares it dynamically from the same
  file.
- Both build scripts read it and stamp it into the executable's metadata.
- The application shows it in the window title and under **Tools → About**, so
  a bug report can carry it.

To release, change `VERSION` and nothing else.


### 1.2 Verification gate

Install the tooling with `pip install -r requirements-dev.txt`, then:

```bash
python -m black --check .
python -m flake8 .
python -m ruff check .
python -m pytest
```

All four must pass. The Qt tests run offscreen via `QT_QPA_PLATFORM`, so no
display is needed and the application is never launched.

[`tests/test_module_size.py`](tests/test_module_size.py) enforces a 400‑line
cap per module. When a module breaches it, split it rather than raising the
cap.


## 2. Development environment setup (Windows)

These instructions assume Windows 10/11 and PowerShell.

1. Install Python 3.11+ from https://www.python.org/.
2. Clone the repository:

   ```powershell
   git clone <this-repo-url>
   cd 3D-Printer-Launcher
   ```

3. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

4. Install runtime dependencies and build‑time tools:

   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install nuitka ordered-set zstandard
   ```

   `requirements-dev.txt` holds the verification tooling (`black`, `flake8`,
   `ruff`, `pytest`) described in section 1.2.

The dashboards are Flask apps served by a production WSGI server (Waitress), so
there is no Flask development server involved at runtime.

Nuitka may require Microsoft C++ Build Tools (MSVC) to be installed. If Nuitka
complains about missing compilers, install the “Desktop development with C++”
workload via Visual Studio or the standalone Build Tools.


## 3. Running the launcher from source

With the `venv` activated, you can run the launcher directly:

```powershell
python main.py
```

The launcher window should appear and you can start/stop the three tools from
there. Logs are written to `launcher_*.log` files in each tool’s project
directory by `AppRunner._log()` in [`runner_widget.py`](runner_widget.py).

On Windows, Stop escalates to a hard kill quickly to ensure the dashboard port
is actually released (so you don't end up with a "stopped" card while the web
server is still listening): `AppRunner.stop()` in [`runner_widget.py`](runner_widget.py).


## 4. Building a single‑file executable with Nuitka

### 4.1 Windows (Python helper – recommended)

From the project root, with your `venv` activated:

```powershell
python build_nuitka.py
```

[`build_nuitka.py`](build_nuitka.py) will:

1. Remove any existing `dist/` directory.
2. Invoke Nuitka as a module with:
   - `--onefile`
   - `--enable-plugin=pyside6`
   - `--windows-console-mode=disable`
   - `--windows-icon-from-ico=filament.ico`
   - `--product-name`, `--product-version` and `--file-version`, all derived
     from the `VERSION` file
   - `--follow-imports`
   - `--output-dir=dist`
   - Entry script: [`main.py`](main.py)

This file holds the one definition of the Windows build.

On success you will get `dist\main.exe`.

### 4.2 Windows (batch file)

Alternatively, you can call the batch script from a normal (non‑venv) Command
Prompt, as long as `python` resolves to an interpreter that has Nuitka and the
project dependencies installed:

```cmd
build_nuitka.cmd
```

It is a thin wrapper that runs [`build_nuitka.py`](build_nuitka.py), so it
cannot drift from section 4.1. It produces the same `dist\main.exe`.

### 4.3 macOS and generic Unix

For macOS and Unix-like systems, the recommended entry point is the generic
shell script [`build_nuitka_unix.sh`](build_nuitka_unix.sh). It uses the same
Nuitka options as the Windows scripts but omits the Windows-only console flag.
By default it runs `python3` but you can override that via `PYTHON_BIN`.

Example (from the repo root, with a virtualenv already prepared):

```bash
./build_nuitka_unix.sh
```

or explicitly:

```bash
PYTHON_BIN=./venv/bin/python ./build_nuitka_unix.sh
```

There is one script for every platform. It detects the package manager
present (`apt`, `dnf`, `pacman`, `xbps-install`, `zypper` or `brew`) and
prints the right system prerequisites for that machine, so Debian, Fedora,
RHEL, Arch, Void, openSUSE and macOS are all covered by the same file.

On success you will get `dist/main` (an ELF or Mach‑O binary depending on the
host OS).


## 5. Expected folder layout for releases

Path resolution is centralised in `_compute_base_dir()` in [`app_spec.py`](app_spec.py). When
running as a Nuitka onefile executable, the launcher:

1. Starts from `sys.argv[0]` (the path of the `.exe`).
2. Probes both the executable’s directory and its parent directory for the
   three tool folders `qidi-temps/`, `qidiwebcamdrestart/` and `VoronTemps/`.
3. Picks the first directory that contains all three.

Two layouts are therefore supported out‑of‑the-box:

1. **Development / repo layout** (what you have in Git):

   ```text
   3D-Printer-Launcher/
     main.py
     app_spec.py
     main_window.py
     runner_widget.py
     styles.py
     requirements.txt
     venv/
     qidi-temps/
     qidiwebcamdrestart/
     VoronTemps/
   ```

2. **Packaged layout** (after Nuitka build):

   ```text
   dist/
     main.exe
   qidi-temps/
   qidiwebcamdrestart/
   VoronTemps/
   venv/
   ```

or alternatively:

```text
main.exe
qidi-temps/
qidiwebcamdrestart/
VoronTemps/
venv/
```

When publishing a new release, package `main.exe` together with the three tool
folders and a pre‑populated `venv/` if you want a fully self‑contained
distribution. If you prefer a lighter download, you can ship only `main.exe`
and the tool folders and ask users to create the `venv` themselves as outlined
in [`README.md`](README.md).


## 6. Modifying or adding tools/printers

Available tools/printers are configured through the Manage dialog and the
per‑user configuration file, not hard‑coded in `main.py`.

Non‑programmer note: if your goal is just "add my printer", use the launcher UI
(Manage printers/tools). You only need the sections below if you want to share a
pre-made configuration or you are changing what sensors the dashboards
display.

### 6.1 Where the configuration lives

The live configuration is per user and is **not** in the repository:

- Windows: `%APPDATA%\3D-Printer-Launcher\tools_config.json`
- Everything else: `$XDG_CONFIG_HOME/3D-Printer-Launcher/tools_config.json`,
  falling back to `~/.config/3D-Printer-Launcher/tools_config.json`

**Tools → Open configuration folder** opens it. Set the
`PRINTER_LAUNCHER_CONFIG_DIR` environment variable to override the location,
which is what the tests do.

[`tools_config.example.json`](tools_config.example.json) is the tracked
template. It holds placeholder addresses only, is copied to the per‑user
location on first run and is never written to. A configuration left beside the
application by an older version is migrated once, then ignored.

### 6.2 Editing via JSON

- Structure is defined by `config.ToolEntry` in [`config.py`](config.py).
- `config.enabled_specs()` and `MainWindow._reload_tools_from_config()` consume
  the file and build corresponding `AppSpec` instances (see [`app_spec.py`](app_spec.py)).

Each entry allows you to configure:

- `label` – UI name of the card.
- `project_dir` and `script` – which backend to run.
- `kind` – `"normal"` vs `"oneshot"` (affects Start/Stop buttons).
- `enabled` – whether the card appears in the launcher.
- `moonraker_host` – the printer's hostname or IP address, nothing more.
- `moonraker_api_port` – the TCP port Moonraker listens on, default `7125`.
- `dashboard_port` – the local port this tool's own web dashboard binds.

The full Moonraker query URL is **derived** from `moonraker_host` and
`moonraker_api_port`, so there is no stored URL that can disagree with the
stored port. Older configurations that hold a `moonraker_url` (and the former
`moonraker_port` name for the dashboard port) are still read and converted on
load.

### 6.3 Editing via the Manage dialog

For most cases you should prefer the UI:

- Open **Tools → Manage printers / tools** or click **Manage printers** in the
  top bar.
- Edit the fields as described in the main [`README.md`](README.md).
- Press **Save changes** – the launcher reloads the config and rebuilds its
  `AppRunner` cards live.

### 6.4 Code‑level changes

If you add tools that have different dependency sets from the existing ones,
consider either:

- Keeping a single, larger `venv` that satisfies all tools or
- Teaching `AppSpec` (see [`app_spec.py`](app_spec.py)) to point at per‑tool virtualenvs and
  adjusting `AppRunner.start()` in [`runner_widget.py`](runner_widget.py) accordingly.


## 7. Licensing

The project’s license is stored in [`LICENSE`](LICENSE). The launcher UI
includes a “View LGPL‑3 License” action wired up in
`MainWindow.open_license()` in [`main_window.py`](main_window.py), which simply opens that
file in the system viewer.

When redistributing binaries you must ship that license file alongside your
executable to comply with the LGPL‑3 terms.

