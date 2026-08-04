"""Shared test fixtures.

The project is a flat set of modules at the repository root rather than an
installed package, so the root goes on ``sys.path`` before anything imports
from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import CONFIG_DIR_ENV_VAR


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Point the configuration at a throwaway directory for one test."""

    target = tmp_path / "config"
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(target))
    return target


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
