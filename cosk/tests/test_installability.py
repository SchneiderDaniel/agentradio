from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


COSK_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_editable_install_from_cosk_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=COSK_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"


@pytest.mark.integration
def test_imports_after_editable_install() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import cosk;"
                "import cosk.extraction;"
                "import cosk.indexing;"
                "import cosk.graph;"
                "import cosk.mcp;"
                "import cosk.safety"
            ),
        ],
        cwd=COSK_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
