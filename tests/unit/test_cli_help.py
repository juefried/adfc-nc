from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from adfc_nc.cli import _COMPLETION_ENV_VARS, clear_completion_environment_for_help

REPO_ROOT = Path(__file__).resolve().parents[2]


def _set_completion_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _COMPLETION_ENV_VARS:
        monkeypatch.setenv(name, "value")


def test_clears_completion_variables_for_help(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_completion_environment(monkeypatch)

    clear_completion_environment_for_help(["--help"])

    for name in _COMPLETION_ENV_VARS:
        assert name not in os.environ


def test_clears_completion_variables_for_short_help(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_completion_environment(monkeypatch)

    clear_completion_environment_for_help(["users", "list", "-h"])

    for name in _COMPLETION_ENV_VARS:
        assert name not in os.environ


def test_keeps_completion_variables_without_help(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_completion_environment(monkeypatch)

    clear_completion_environment_for_help(["users", "list"])

    for name in _COMPLETION_ENV_VARS:
        assert os.environ[name] == "value"


def test_module_help_works_with_stale_completion_environment() -> None:
    env = os.environ.copy()
    env.update(
        {
            "_ADFC_NC_COMPLETE": "complete_powershell",
            "_TYPER_COMPLETE_ARGS": "adfc-nc ",
            "_TYPER_COMPLETE_WORD_TO_COMPLETE": "list",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    existing_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPO_ROOT / "src")
        if not existing_path
        else os.pathsep.join([str(REPO_ROOT / "src"), existing_path])
    )

    completed = subprocess.run(
        [sys.executable, "-m", "adfc_nc", "--help"],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=REPO_ROOT,
        check=False,
    )

    assert completed.returncode == 0
    assert "Usage" in completed.stdout
    assert "Options" in completed.stdout
