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


class TestUninstallData:
    def test_remove_deletes_directory(self, tmp_path):
        """uninstall_data(remove=True) should delete the DB directory."""
        db_dir = tmp_path / "context-memory"
        db_dir.mkdir()
        (db_dir / "context.db").write_bytes(b"fake db")

        with patch.object(uninstall, "DB_DIR", db_dir):
            result = uninstall.uninstall_data(remove=True)

        assert result == "Database: removed"
        assert not db_dir.exists()

    def test_preserve_keeps_directory(self, tmp_path):
        """uninstall_data(remove=False) should preserve the DB directory."""
        db_dir = tmp_path / "context-memory"
        db_dir.mkdir()
        (db_dir / "context.db").write_bytes(b"fake db")

        with patch.object(uninstall, "DB_DIR", db_dir):
            result = uninstall.uninstall_data(remove=False)

        assert "preserved" in result
        assert db_dir.exists()

    def test_no_data_found(self, tmp_path):
        """uninstall_data() should report no data when directory doesn't exist."""
        db_dir = tmp_path / "context-memory"

        with patch.object(uninstall, "DB_DIR", db_dir):
            result = uninstall.uninstall_data(remove=True)

        assert result == "Database: no data found"


class TestUninstallSkill:
    def test_removes_directory(self, tmp_path):
        """Should remove the skill directory."""
        skill_dst = tmp_path / "skills" / "context-memory"
        skill_dst.mkdir(parents=True)
        (skill_dst / "SKILL.md").write_text("# Skill", encoding="utf-8")

        with patch.object(uninstall, "SKILL_DST", skill_dst):
            result = uninstall.uninstall_skill()

        assert result == "Skill: removed"
        assert not skill_dst.exists()

    def test_removes_symlink(self, tmp_path):
        """Should remove a symlinked skill."""
        target = tmp_path / "target"
        target.mkdir()
        skill_dst = tmp_path / "skills" / "context-memory"
        skill_dst.parent.mkdir(parents=True)
        skill_dst.symlink_to(target, target_is_directory=True)

        with patch.object(uninstall, "SKILL_DST", skill_dst):
            result = uninstall.uninstall_skill()

        assert result == "Skill: symlink removed"
        assert not skill_dst.exists()
        # Original target should still exist
        assert target.exists()

    def test_not_installed(self, tmp_path):
        """Should report not installed when directory doesn't exist."""
        skill_dst = tmp_path / "skills" / "context-memory"

        with patch.object(uninstall, "SKILL_DST", skill_dst):
            result = uninstall.uninstall_skill()

        assert result == "Skill: not installed"


class TestUninstallHooks:
    def _write_settings(self, path, settings):
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def test_removes_our_hook(self, tmp_path):
        """Should remove context-memory hooks from settings.json."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "python ~/.claude/skills/context-memory/scripts/auto_save.py"}]}
                ]
            }
        }
        self._write_settings(settings_path, settings)

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert "Hooks: removed Stop from settings.json" == result
        updated = json.loads(settings_path.read_text(encoding="utf-8"))
        # hooks key should be cleaned up entirely
        assert "hooks" not in updated

    def test_preserves_other_hooks(self, tmp_path):
        """Should keep non-context-memory hooks in place."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "python ~/.claude/skills/context-memory/scripts/auto_save.py"}]},
                    {"hooks": [{"type": "command", "command": "python /some/other/plugin/hook.py"}]},
                ]
            }
        }
        self._write_settings(settings_path, settings)

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert "Hooks: removed Stop from settings.json" == result
        updated = json.loads(settings_path.read_text(encoding="utf-8"))
        assert len(updated["hooks"]["Stop"]) == 1
        assert "other/plugin" in updated["hooks"]["Stop"][0]["hooks"][0]["command"]

    def test_no_settings_file(self, tmp_path):
        """Should report not found when settings.json doesn't exist."""
        settings_path = tmp_path / "settings.json"

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert result == "Hooks: settings.json not found"

    def test_malformed_settings_json(self, tmp_path):
        """Should handle malformed settings.json gracefully."""
        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{invalid json", encoding="utf-8")

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert result == "Hooks: settings.json is malformed, skipped"

    def test_no_stop_hooks(self, tmp_path):
        """Should report no Stop hooks when hooks section is empty."""
        settings_path = tmp_path / "settings.json"
        self._write_settings(settings_path, {"hooks": {}})

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert result == "Hooks: no hooks found"

    def test_not_installed(self, tmp_path):
        """Should report not installed when Stop hooks exist but none are ours."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "python /other/hook.py"}]}
                ]
            }
        }
        self._write_settings(settings_path, settings)

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert result == "Hooks: not installed"

    def test_cleans_empty_hooks_structure(self, tmp_path):
        """Should remove empty hooks/Stop keys after removing our hook."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "python ~/.claude/skills/context-memory/scripts/auto_save.py"}]}
                ]
            },
            "other_setting": True,
        }
        self._write_settings(settings_path, settings)

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            uninstall.uninstall_hooks()

        updated = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "hooks" not in updated
        assert updated["other_setting"] is True

    def test_matches_windows_expanded_path(self, tmp_path):
        """Should recognize hooks with Windows expanded paths."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "python C:/Users/Test/.claude/skills/context-memory/scripts/auto_save.py"}]}
                ]
            }
        }
        self._write_settings(settings_path, settings)

        with patch.object(uninstall, "SETTINGS_PATH", settings_path):
            result = uninstall.uninstall_hooks()

        assert "Hooks: removed Stop from settings.json" == result
