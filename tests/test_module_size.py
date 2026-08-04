"""The one structural rule this project enforces: module size.

The project is a flat set of modules with no layering to assert, so a size
cap is the rule that actually catches drift. A module that grows past the cap
is the signal to split it, which is what happened to the Manage dialog and
the Voron dashboard.
"""

from __future__ import annotations

# Maximum lines in any one module.
MAX_MODULE_LINES = 400

# The band just below the cap. A module in here is one edit from breaching it,
# so it is reported as a warning rather than waiting for the failure.
DANGER_BAND_START = 380

# Directories that hold no first-party source.
EXCLUDED_DIRS = {"venv", "dist", "build", "docs", ".ruff_cache", "__pycache__"}


def _source_files(repo_root):
    for path in sorted(repo_root.rglob("*.py")):
        if EXCLUDED_DIRS.isdisjoint(part for part in path.parts):
            yield path


def _line_count(path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_there_is_source_to_measure(repo_root):
    """Guards against the discovery above silently matching nothing."""

    assert list(_source_files(repo_root))


def test_no_module_exceeds_the_size_cap(repo_root):
    oversized = {
        path.name: _line_count(path)
        for path in _source_files(repo_root)
        if _line_count(path) > MAX_MODULE_LINES
    }
    assert not oversized, (
        f"Modules over {MAX_MODULE_LINES} lines: {oversized}. Split them "
        "rather than raising the cap."
    )


def test_report_modules_approaching_the_cap(repo_root, capsys):
    """Not a failure: surfaces the modules that are nearly over."""

    approaching = {
        path.name: _line_count(path)
        for path in _source_files(repo_root)
        if DANGER_BAND_START <= _line_count(path) <= MAX_MODULE_LINES
    }
    if approaching:
        print(f"Modules within the danger band: {approaching}")
    with capsys.disabled():
        assert isinstance(approaching, dict)
