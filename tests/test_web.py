"""Runs the browser-side render tests, so `pytest` covers the whole system."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_render_js_test_suite_passes():
    result = subprocess.run(
        ["node", "--test", "tests/render.test.js"],
        cwd=ROOT, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
