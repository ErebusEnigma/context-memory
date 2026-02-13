"""Shared test fixtures for context-memory tests."""

import os
import sys

import pytest

# Add scripts directory to path so tests can import modules
SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "context-memory", "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Use a temporary database for every test."""
    import db_init
    import db_utils
    db_path = tmp_path / "context.db"
    monkeypatch.setattr(db_utils, "DB_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    # db_init imports DB_PATH separately, so patch it there too
    monkeypatch.setattr(db_init, "DB_PATH", db_path)
    yield db_path
