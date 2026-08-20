"""Shared test setup.

Tests must never depend on the live glossary: it is gitignored user data that
differs from machine to machine, so a suite that reads it passes or fails for
reasons unrelated to the code. Everything here points at the shipped example.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_GLOSSARY = ROOT / "glossary" / "terms.example.yaml"


@pytest.fixture
def example_config(tmp_path):
    """A Config pinned to the shipped example glossary and a temp transcript dir."""
    from salm.config import Config

    config = Config()
    config.glossary = EXAMPLE_GLOSSARY
    config.transcript_dir = tmp_path
    return config
