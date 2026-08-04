"""Guards the repository against shipping somebody's actual network.

This is the regression test for the defect that started this work: the
tracked configuration named a specific host on a specific LAN, so anyone who
cloned the repository got a launcher pointed at a stranger's device.
"""

from __future__ import annotations

import re

# Any dotted quad that is not a documentation or loopback address. Hostnames
# are not checked: a placeholder like "printer.local" is fine and a real one
# cannot be told apart from it automatically.
IP_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")

# Addresses that are legitimate to have in the tree.
ALLOWED_ADDRESSES = {
    # Loopback: every dashboard binds here by default.
    "127.0.0.1",
    # "Bind to everything", used in documentation of the host argument.
    "0.0.0.0",
}

# Extensions worth scanning. Binary assets cannot carry a config address.
SCANNED_SUFFIXES = {".py", ".json", ".md", ".toml", ".cmd", ".sh", ".flake8", ""}

EXCLUDED_DIRS = {
    "venv",
    "dist",
    "build",
    ".git",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
    # The site is generated content and holds no launcher configuration.
    "docs",
    # The suite itself uses example addresses on purpose, including this file.
    "tests",
}

# The live configuration is untracked and the developer's own copy of it may
# legitimately sit in the working tree while holding a real address.
EXCLUDED_FILES = {"tools_config.json"}


def _scanned_files(repo_root):
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if not EXCLUDED_DIRS.isdisjoint(path.parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        yield path


def _offending_addresses(text: str) -> set[str]:
    found = set()
    for match in IP_RE.finditer(text):
        address = match.group(0)
        if address in ALLOWED_ADDRESSES:
            continue
        # A version like 1.2.3.4 is not an address; those live in VERSION and
        # are only three components, so a four-part match is a real quad.
        if any(int(part) > 255 for part in match.groups()):
            continue
        found.add(address)
    return found


def test_there_are_files_to_scan(repo_root):
    """Guards against the discovery above silently matching nothing."""

    assert list(_scanned_files(repo_root))


def test_no_tracked_file_carries_a_real_ip_address(repo_root):
    offenders = {}
    for path in _scanned_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = _offending_addresses(text)
        if found:
            offenders[str(path.relative_to(repo_root))] = sorted(found)

    assert not offenders, (
        f"Real network addresses found in tracked files: {offenders}. "
        "Printer addresses belong in the user's own configuration."
    )
