"""Tests for uninstall.py."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uninstall


class TestHookMatches:
    def test_matches_forward_slash_path(self):
        cmd = "python C:/Users/Test/.claude/skills/context-memory/scripts/auto_save.py"
        assert uninstall._hook_matches(cmd) is True

    def test_matches_backslash_path(self):
        """Backslash paths (Windows) should match after normalization."""
        cmd = "python C:\\Users\\Test\\.claude\\skills\\context-memory\\scripts\\auto_save.py"
        assert uninstall._hook_matches(cmd) is True

    def test_matches_mixed_slash_path(self):
        cmd = "python C:\\Users\\Test/.claude/skills\\context-memory/scripts\\db_save.py"
        assert uninstall._hook_matches(cmd) is True

    def test_rejects_unrelated_command(self):
        cmd = "python /some/other/plugin/scripts/save.py"
        assert uninstall._hook_matches(cmd) is False


class TestUninstallCommands:
    def test_removes_matching_files(self, tmp_path):
        """Normal uninstall should remove files that match source content."""
        commands_dst = tmp_path / "commands"
        commands_dst.mkdir()
        commands_src = tmp_path / "src_commands"
        commands_src.mkdir()

        content = "# remember command"
        (commands_dst / "remember.md").write_text(content, encoding="utf-8")
        (commands_src / "remember.md").write_text(content, encoding="utf-8")

        with patch.object(uninstall, "COMMANDS_DST", commands_dst), \
             patch.object(uninstall, "COMMANDS_SRC", commands_src), \
             patch.object(uninstall, "OUR_COMMAND_FILES", ["remember.md"]):
            result = uninstall.uninstall_commands()

        assert "removed" in result
        assert not (commands_dst / "remember.md").exists()

    def test_skips_modified_files_without_force(self, tmp_path):
        """Modified files should be skipped without --force, with a warning."""
        commands_dst = tmp_path / "commands"
        commands_dst.mkdir()
        commands_src = tmp_path / "src_commands"
        commands_src.mkdir()

        (commands_dst / "remember.md").write_text("modified by user", encoding="utf-8")
        (commands_src / "remember.md").write_text("original content", encoding="utf-8")

        with patch.object(uninstall, "COMMANDS_DST", commands_dst), \
             patch.object(uninstall, "COMMANDS_SRC", commands_src), \
             patch.object(uninstall, "OUR_COMMAND_FILES", ["remember.md"]):
            result = uninstall.uninstall_commands(force=False)

        assert "skipped" in result
        assert "--force" in result
        assert "orphan files remain" in result
        assert (commands_dst / "remember.md").exists()

    def test_force_removes_modified_files(self, tmp_path):
        """With --force, modified files should be removed anyway."""
        commands_dst = tmp_path / "commands"
        commands_dst.mkdir()
        commands_src = tmp_path / "src_commands"
        commands_src.mkdir()

        (commands_dst / "remember.md").write_text("modified by user", encoding="utf-8")
        (commands_src / "remember.md").write_text("original content", encoding="utf-8")

        with patch.object(uninstall, "COMMANDS_DST", commands_dst), \
             patch.object(uninstall, "COMMANDS_SRC", commands_src), \
             patch.object(uninstall, "OUR_COMMAND_FILES", ["remember.md"]):
            result = uninstall.uninstall_commands(force=True)

        assert "removed" in result
        assert "orphan" not in result
        assert not (commands_dst / "remember.md").exists()


class TestUninstallMcp:
    def test_removes_entry(self, tmp_path):
        """Should remove the context-memory entry from mcp_servers.json."""
        config_path = tmp_path / "mcp_servers.json"
        config = {
            "context-memory": {"command": "python", "args": ["server.py"]},
            "other-server": {"command": "node", "args": ["index.js"]},
        }
        config_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(uninstall, "MCP_CONFIG_PATH", config_path):
            result = uninstall.uninstall_mcp()

        assert "removed" in result
        remaining = json.loads(config_path.read_text(encoding="utf-8"))
        assert "context-memory" not in remaining
        assert "other-server" in remaining

    def test_deletes_file_when_empty(self, tmp_path):
        """Should delete mcp_servers.json entirely if it becomes empty."""
        config_path = tmp_path / "mcp_servers.json"
        config = {"context-memory": {"command": "python", "args": ["server.py"]}}
        config_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(uninstall, "MCP_CONFIG_PATH", config_path):
            result = uninstall.uninstall_mcp()

        assert "removed" in result
        assert not config_path.exists()

    def test_not_registered(self, tmp_path):
        """Should report not registered when entry is missing."""
        config_path = tmp_path / "mcp_servers.json"
        config_path.write_text(json.dumps({"other": {}}), encoding="utf-8")

        with patch.object(uninstall, "MCP_CONFIG_PATH", config_path):
            result = uninstall.uninstall_mcp()

        assert "not registered" in result

    def test_no_config_file(self, tmp_path):
        """Should report not found when mcp_servers.json doesn't exist."""
        config_path = tmp_path / "mcp_servers.json"

        with patch.object(uninstall, "MCP_CONFIG_PATH", config_path):
            result = uninstall.uninstall_mcp()

        assert "not found" in result
