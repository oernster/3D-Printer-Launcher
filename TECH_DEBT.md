# 3D Printer Launcher: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository: the launcher at root, the three bundled tools (`VoronTemps/`, `qidi-temps/`, `qidiwebcamdrestart/`), the build scripts and the GitHub Pages site under `docs/`.

This is a small tool (roughly 2,300 lines across eleven modules) and the file is short in proportion. It is also the least-protected project in the portfolio: there is no test suite, no coverage gate, no structural test and no `VERSION` file.

---

## 1. `tools_config.json` ships the author's own network as the default configuration

The tracked config names a specific host on a specific LAN, repeated across every tool entry:

```json
"moonraker_url": "http://192.168.1.120:7125/printer/objects/query"
```

Two consequences, and the second is the one that matters:

- Anyone who clones this repository gets a launcher pointed at `192.168.1.120`, which on their network is either nothing or somebody else's device. The first run fails, or worse, quietly queries an unrelated host.
- The file is the *live* config, not an example. So the author's own working configuration and the repository's shipped default are the same file, which means every local change to a printer address is a pending git modification, and the obvious way to make that go away is to commit it.

Split them: ship `tools_config.example.json` with placeholder addresses, have the launcher copy it to a per-user location (`%APPDATA%` or `~/.config/`) on first run and read from there, and untrack the live file. That is the same local-first pattern every other application in the portfolio already uses for its settings, and it removes the personal network detail from a public repository as a side effect.

While in there: each entry carries `moonraker_url`, `moonraker_port` and `moonraker_api_port`, and the URL already contains the port. Three fields encoding one fact means they can disagree, and nothing says which wins.

## 2. There are no tests at all

Eleven Python modules, zero test files, no `pytest` configuration and no coverage of any kind. This is the only project surfaced on the site with no automated verification whatsoever.

That would be defensible for a pure GUI shell. It is not one. The launcher spawns subprocesses, polls Moonraker over HTTP, parses JSON responses, manages tool lifecycle and writes configuration. `config.py` and the tool-definition handling in `manage_tools_dialog.py` are plain data logic with no Qt in them.

The proportionate target is not a 100% gate over the tree. It is a handful of tests over the parts that decide: config load and save (including the malformed-file path), the tool-definition validation and whatever the Moonraker response parsing does with an unexpected shape. That is an afternoon and it covers the code most likely to fail on someone else's printer.

## 3. Twenty broad exception handlers, none with a stated reason

Concentrated in `VoronTemps/app.py` (ten), `manage_tools_dialog.py` (three), `runner_widget.py` (three) and `config.py` (two).

The ones in `VoronTemps/app.py` and `runner_widget.py` are on the network-poll and subprocess-management paths, where degrading rather than crashing is correct: a printer that is powered off should grey out a panel, not take down the launcher. Those need one line each saying what they fall back to.

The two in `config.py` are different and worth looking at properly. A swallowed exception during config load means the launcher starts with defaults instead of the user's tools, with no indication that their configuration was not read. Given item 1, that failure is also silent about *which* file it failed on.

## 4. Six near-identical distro build wrappers

`build_nuitka_arch.sh`, `build_nuitka_debian.sh`, `build_nuitka_fedora.sh`, `build_nuitka_rhel.sh`, `build_nuitka_void.sh` and `build_nuitka_macos.sh` are each 19 or 20 lines, and they wrap the one real script, `build_nuitka_unix.sh` (39 lines). A diff between any two shows the only substantive difference is the package-manager line in the prerequisites comment (`apt install` versus `dnf install` and so on).

Six files to update when the build changes, five of which nobody will notice are stale because most people are on one distro. Collapse them into one wrapper that detects the package manager (`pacman`, `apt`, `dnf`, `xbps-install`, `brew`) and prints the right prerequisite line, which is a dozen lines and one file to maintain.

`build_nuitka.py` and `build_nuitka.cmd` cover Windows and should stay.

## 5. No `VERSION` file and no version anywhere

There is no `VERSION`, no `version.py` and no version string in the tree. The application is packaged with Nuitka and distributed, so it ships with no way for a user to say which build they are running.

Add a `VERSION` file at root, read it from a small `version.py` with a `0.0.0-dev` fallback, and surface it in the window title or an About entry. The build scripts should read the same file for the PE metadata.

## 6. `manage_tools_dialog.py` is over the module cap, and nothing measures it

At 457 lines it exceeds 400. `VoronTemps/app.py` at 393 sits inside the 381 to 399 danger band, so its next edit takes it over too.

There is no structural test, so neither is reported anywhere. Given the project's size, a single size assertion is more valuable than a full structural suite would be: it is the one rule that catches drift without needing a layering the project does not have.

## 7. The three bundled tools are vendored copies with no shared code

`VoronTemps/`, `qidi-temps/` and `qidiwebcamdrestart/` each hold their own `app.py` (or `webcamdrestart.py`) and each independently talks to Moonraker.

That independence is partly deliberate and good: each tool is launched as a separate process and must run standalone. But the Moonraker query, the response parsing and the error handling now exist in three places, and `qidi-temps/app.py` has one broad handler where `VoronTemps/app.py` has ten, which suggests the three have already diverged in how carefully they behave.

A small shared module for "query Moonraker and return a parsed reading", imported by all three, keeps them independently launchable while giving them one implementation to fix and one place for item 2's tests to land.

---

## Looks like debt, not worth touching

- The flat module layout at root (`main.py`, `main_window.py`, `config.py`, `styles.py`, `runner_widget.py`, `manage_tools_dialog.py`) with no package and no `domain`/`application`/`infrastructure` split. At 2,300 lines with one clear job, six cohesive modules is the proportionate structure. Items 2 and 6 ask for tests and a size rule, not for four directories.
- `app_spec.py` at root beside the Nuitka scripts. Packaging metadata.
- The three `.gitignore` files (root plus subdirectories). Each covers its own tool's artefacts.
- `SETUP_NEW_PRINTER.md` alongside `DEVELOPMENT_README.md`. Distinct subjects: one is for users adding a printer, one is for building.
- The eight tracked PNGs plus the two `.ico` files. Icon assets for the launcher and the site.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **Launching each tool as a separate process rather than importing it.** A hung Moonraker poll or a crashed tool must not take the launcher with it. Process isolation is the whole design and item 7 does not weaken it.
- **Nuitka rather than PyInstaller.** The portfolio's choice for production runtime applications.
- **`qidiwebcamdrestart` being a one-shot tool with a different lifecycle from the polling tools**, expressed as `"kind": "oneshot"` in the config. Correctly modelled.
- **LGPL-3.0.** Aligned with the Qt front end, and deliberate.
