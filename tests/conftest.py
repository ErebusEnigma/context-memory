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
    import db_save
    import db_utils
    db_path = tmp_path / "context.db"
    monkeypatch.setattr(db_utils, "DB_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    # Modules that import DB_PATH at module level need patching too
    monkeypatch.setattr(db_init, "DB_PATH", db_path)
    monkeypatch.setattr(db_save, "DB_PATH", db_path, raising=False)
    # Patch db_prune if it has been imported
    try:
        import db_prune
        monkeypatch.setattr(db_prune, "DB_PATH", db_path, raising=False)
    except ImportError:
        pass
    # Patch mcp_server if it has been imported (requires optional mcp package)
    try:
        import mcp_server  # noqa: F811
        monkeypatch.setattr(mcp_server, "DB_PATH", db_path, raising=False)
    except (ImportError, SystemExit):
        pass
    # Patch dashboard if it has been imported (requires optional flask package)
    try:
        import dashboard  # noqa: F811
        monkeypatch.setattr(dashboard, "DB_PATH", db_path, raising=False)
    except (ImportError, SystemExit):
        pass
    yield db_path
