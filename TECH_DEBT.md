# 3D Printer Launcher: Technical Debt

A standing reference to the project's outstanding technical debt. It records
what is still open, weighs whether each item is worth doing and gives the
rationale. Every item is a behaviour-preserving internal concern: nothing here
proposes reverting a feature or changing any UI or UX behaviour. Scope is the
whole repository: the launcher at root, the three bundled tools
(`VoronTemps/`, `qidi-temps/`, `qidiwebcamdrestart/`), the build scripts and
the GitHub Pages site under `docs/`.

This is a small project (roughly 3,400 lines across nineteen modules, plus a
test suite). It has a `VERSION` file read by both the application and the build
scripts, a `pytest` suite covering the configuration and Moonraker logic, an
offscreen smoke test over the Qt layer, a structural size rule, a
`requirements.txt` that names the five packages the code imports rather than a
frozen snapshot of one machine, plus a GitHub Actions workflow that runs the
whole gate on every push and pull request.

**There is no open technical debt.** The two sections below are the standing
record of what was weighed and deliberately left alone, so the same ground is
not covered again.

---

## Looks like debt, not worth touching

- The flat module layout at root with no package and no
  `domain`/`application`/`infrastructure` split. At this size with one clear
  job, cohesive flat modules are the proportionate structure; the size rule in
  `tests/test_module_size.py` is what actually keeps them honest.
- `app_spec.py` at root beside the Nuitka scripts. Packaging metadata.
- The three `.gitignore` files (root plus subdirectories). Each covers its own
  tool's artefacts.
- `SETUP_NEW_PRINTER.md` alongside `DEVELOPMENT_README.md`. Distinct subjects:
  one is for users adding a printer, one is for building.
- The tracked PNGs plus the `.ico` files. Icon assets for the launcher and the
  site.
- The Qt widgets having smoke coverage rather than full behavioural coverage.
  Asserting on rendered appearance is fragile and low value; the smoke tests
  cover the failure mode that has actually occurred, which is construction
  raising.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would
regress or add cost for nothing.

- **Launching each tool as a separate process rather than importing it.** A
  hung Moonraker poll or a crashed tool must not take the launcher with it.
  Process isolation is the whole design; the shared `moonraker.py` and
  `moonraker_client.py` modules do not weaken it: each tool still starts
  standalone and puts the launcher root on `sys.path` itself.
- **The `sys.path` insertion at the top of each bundled tool.** It is the
  consequence of the process isolation above; it is why those three files
  carry an `E402` exemption in both `.flake8` and `pyproject.toml`.
- **`moonraker.py` being standard library only, with `aiohttp` confined to
  `moonraker_client.py`.** This keeps `aiohttp` out of the launcher's own
  import graph and therefore out of the Nuitka build.
- **Nuitka rather than PyInstaller.** The portfolio's choice for production
  runtime applications.
- **`qidiwebcamdrestart` being a one-shot tool with a different lifecycle from
  the polling tools**, expressed as `"kind": "oneshot"` in the configuration.
  Correctly modelled.
- **`paramiko.AutoAddPolicy` in the webcam helper.** The target is the user's
  own printer on their own LAN, at an address they typed in themselves; its
  firmware regenerates its host key on reflash. Carries an explicit
  `# noqa: S507` recording the reasoning.
- **LGPL-3.0.** Aligned with the Qt front end and deliberate.
