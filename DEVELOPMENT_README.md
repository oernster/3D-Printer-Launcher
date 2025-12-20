# 3D‑Printer‑Launcher – Developer Guide

This document is for contributors and power users who want to build or modify
the launcher executable themselves. End‑users can simply download the latest
`.exe` from this repository’s GitHub Releases page and follow
[`README.md`](README.md:1).


## 1. Project overview

- Launcher entry point: [`main.py`](main.py:1)
- Tool specification and path handling: [`app_spec.py`](app_spec.py:1)
- Persistent tool/printer config model:
  [`config.ToolEntry`](config.py:13), [`config.load_tools_config()`](config.py:68)
- Main window UI: [`main_window.MainWindow()`](main_window.py:28)
- Per‑tool runner widget: [`runner_widget.AppRunner()`](runner_widget.py:21)
- Tools/printers management dialog:
  [`manage_tools_dialog.ManageToolsDialog()`](manage_tools_dialog.py:28)
- Shared styling: [`styles.py`](styles.py:1)
- Nuitka build helper script: [`build_nuitka.py`](build_nuitka.py:1)
- Windows build convenience wrapper: [`build_nuitka.cmd`](build_nuitka.cmd:1)
- Unix/macOS build scripts: [`build_nuitka_unix.sh`](build_nuitka_unix.sh:1), [`build_nuitka_macos.sh`](build_nuitka_macos.sh:1)
- Linux distro-specific wrappers: [`build_nuitka_debian.sh`](build_nuitka_debian.sh:1), [`build_nuitka_arch.sh`](build_nuitka_arch.sh:1), [`build_nuitka_fedora.sh`](build_nuitka_fedora.sh:1), [`build_nuitka_rhel.sh`](build_nuitka_rhel.sh:1), [`build_nuitka_void.sh`](build_nuitka_void.sh:1)

At runtime `main.build_specs()` in [`main.py`](main.py:13) declares which tools
are available:

- Qidi Temps: [`qidi-temps/app.py`](qidi-temps/app.py:1)
- Qidi `webcamd` restart: [`qidiwebcamdrestart/webcamdrestart.py`](qidiwebcamdrestart/webcamdrestart.py:1)
- Voron Temps: [`VoronTemps/app.py`](VoronTemps/app.py:1)

The base directory detection and log‑file naming live in
[`app_spec._compute_base_dir()`](app_spec.py:9) and
[`AppSpec`](app_spec.py:59).


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
   pip install nuitka ordered-set zstandard
   ```

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
directory by [`AppRunner._log()`](runner_widget.py:156).

On Windows, Stop escalates to a hard kill quickly to ensure the dashboard port
is actually released (so you don’t end up with a “stopped” card while the web
server is still listening): [`AppRunner.stop()`](runner_widget.py:160).


## 4. Building a single‑file executable with Nuitka

### 4.1 Windows (Python helper – recommended)

From the project root, with your `venv` activated:

```powershell
python build_nuitka.py
```

[`build_nuitka.py`](build_nuitka.py:1) will:

1. Remove any existing `dist/` directory.
2. Invoke Nuitka as a module with the options mirrored from
   [`build_nuitka.cmd`](build_nuitka.cmd:1):
   - `--onefile`
   - `--enable-plugin=pyside6`
   - `--windows-console-mode=disable`
   - `--follow-imports`
   - `--output-dir=dist`
   - Entry script: [`main.py`](main.py:1)

On success you will get `dist\main.exe`.

### 4.2 Windows (batch file)

Alternatively, you can call the batch script directly from a normal (non‑venv)
Command Prompt, as long as `python` resolves to a Python interpreter that has
Nuitka and the project dependencies installed:

```cmd
build_nuitka.cmd
```

This runs the same Nuitka command as in section 4.1 and also produces
`dist\main.exe`.

### 4.3 macOS and generic Unix

For macOS and Unix-like systems, the recommended entry point is the generic
shell script [`build_nuitka_unix.sh`](build_nuitka_unix.sh:1). It uses the same
Nuitka options as the Windows scripts but omits the Windows-only console flag.
By default it runs `python3`, but you can override that via `PYTHON_BIN`.

Example (from the repo root, with a virtualenv already prepared):

```bash
./build_nuitka_unix.sh
```

or explicitly:

```bash
PYTHON_BIN=./venv/bin/python ./build_nuitka_unix.sh
```

There are also small convenience wrappers for specific platforms and
distributions:

- macOS: [`build_nuitka_macos.sh`](build_nuitka_macos.sh:1)
- Debian / Ubuntu / Mint: [`build_nuitka_debian.sh`](build_nuitka_debian.sh:1)
- Arch / Manjaro: [`build_nuitka_arch.sh`](build_nuitka_arch.sh:1)
- Fedora: [`build_nuitka_fedora.sh`](build_nuitka_fedora.sh:1)
- RHEL / CentOS / Rocky / AlmaLinux: [`build_nuitka_rhel.sh`](build_nuitka_rhel.sh:1)
- Void Linux: [`build_nuitka_void.sh`](build_nuitka_void.sh:1)

All of these wrappers simply invoke
[`build_nuitka_unix.sh`](build_nuitka_unix.sh:1) after providing comments on the
typical package installation commands for that platform.

On success you will get `dist/main` (an ELF or Mach‑O binary depending on the
host OS).


## 5. Expected folder layout for releases

Path resolution is centralised in [`_compute_base_dir()`](app_spec.py:9). When
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
in [`README.md`](README.md:24).


## 6. Modifying or adding tools/printers

Available tools/printers are now configured via `tools_config.json` and the
Manage dialog, not hard‑coded in `main.py`.

### 6.1 Editing via JSON

- Structure is defined by [`config.ToolEntry`](config.py:13).
- Top‑level file lives next to `main.py` as
  [`tools_config.json`](tools_config.json:1).
- `main.build_specs()` and `MainWindow._reload_tools_from_config()` consume
  this file and build corresponding [`AppSpec`](app_spec.py:59) instances.

Each entry allows you to configure:

- `label` – UI name of the card.
- `project_dir` and `script` – which backend to run.
- `kind` – `"normal"` vs `"oneshot"` (affects Start/Stop buttons).
- `enabled` – whether the card appears in the launcher.
- `moonraker_url`, `moonraker_api_port`, `moonraker_port` – per‑printer
  Moonraker and dashboard configuration for Klipper printers.

### 6.2 Editing via the Manage dialog

For most cases you should prefer the UI:

- Open **Tools → Manage printers / tools** or click **Manage printers** in the
  top bar.
- Edit the fields as described in the main [`README`](README.md:1).
- Press **Save changes** – the launcher reloads the config and rebuilds its
  `AppRunner` cards live.

### 6.3 Code‑level changes

If you add tools that have different dependency sets from the existing ones,
consider either:

- Keeping a single, larger `venv` that satisfies all tools, or
- Teaching [`AppSpec`](app_spec.py:59) to point at per‑tool virtualenvs and
  adjusting [`AppRunner.start()`](runner_widget.py:110) accordingly.


## 7. Licensing

The project’s license is stored in [`LICENSE`](LICENSE:1). The launcher UI
includes a “View LGPL‑3 License” action wired up in
[`MainWindow.open_license()`](main_window.py:216), which simply opens that
file in the system viewer.

When redistributing binaries you must ship that license file alongside your
executable to comply with the LGPL‑3 terms.

