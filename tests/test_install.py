"""Tests for install.py hook and MCP logic."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import install


class TestPlatformHookCommand:
    def test_expands_tilde_on_windows(self):
        """On Windows, ~ should be replaced with the full home path."""
        with patch("install.platform.system", return_value="Windows"), \
             patch("install.Path.home", return_value=Path("C:/Users/TestUser")):
            result = install._platform_hook_command(
                "python ~/.claude/skills/context-memory/scripts/auto_save.py"
            )
        assert result == "python C:/Users/TestUser/.claude/skills/context-memory/scripts/auto_save.py"

    def test_no_op_on_unix(self):
        """On Linux/macOS, ~ should remain unchanged."""
        with patch("install.platform.system", return_value="Linux"):
            result = install._platform_hook_command(
                "python ~/.claude/skills/context-memory/scripts/auto_save.py"
            )
        assert result == "python ~/.claude/skills/context-memory/scripts/auto_save.py"

    def test_backslashes_normalized_in_home_path(self):
        """Windows home path backslashes should become forward slashes."""
        with patch("install.platform.system", return_value="Windows"), \
             patch("install.Path.home", return_value=Path("C:\\Users\\TestUser")):
            result = install._platform_hook_command("python ~/.claude/scripts/test.py")
        assert "\\" not in result
        assert "C:/Users/TestUser/.claude/scripts/test.py" in result

    def test_no_tilde_unchanged(self):
        """Commands without ~ should pass through unchanged on any platform."""
        cmd = "python /absolute/path/to/script.py"
        with patch("install.platform.system", return_value="Windows"):
            assert install._platform_hook_command(cmd) == cmd


class TestHookMatches:
    def test_matches_old_bash_hook(self):
        cmd = "test -f ~/.claude/skills/context-memory/scripts/db_save.py && stuff"
        assert install._hook_matches(cmd) is True

    def test_matches_new_auto_save_hook(self):
        cmd = "python ~/.claude/skills/context-memory/scripts/auto_save.py"
        assert install._hook_matches(cmd) is True

    def test_matches_expanded_path(self):
        cmd = "python C:/Users/TestUser/.claude/skills/context-memory/scripts/auto_save.py"
        assert install._hook_matches(cmd) is True

    def test_rejects_unrelated_hook(self):
        cmd = "python ~/.claude/skills/other-plugin/scripts/save.py"
        assert install._hook_matches(cmd) is False

    def test_matches_backslash_paths(self):
        """Backslash paths (Windows) should still match after normalization."""
        cmd = "python C:\\Users\\TestUser\\.claude\\skills\\context-memory\\scripts\\auto_save.py"
        assert install._hook_matches(cmd) is True

    def test_matches_mixed_slash_paths(self):
        """Mixed forward/backslash paths should still match."""
        cmd = "python C:\\Users\\TestUser/.claude/skills\\context-memory/scripts\\db_save.py"
        assert install._hook_matches(cmd) is True


class TestInstallHooksUpgrade:
    def _write_settings(self, settings_path, hook_command):
        """Write a settings.json with a single stop hook."""
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": hook_command}]}
                ]
            }
        }
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def test_upgrades_outdated_hook(self, tmp_path):
        """Installer should update an existing hook with ~ to the expanded path on Windows."""
        settings_path = tmp_path / "settings.json"
        old_cmd = "python ~/.claude/skills/context-memory/scripts/auto_save.py"
        self._write_settings(settings_path, old_cmd)

        with patch.object(install, "SETTINGS_PATH", settings_path), \
             patch("install.platform.system", return_value="Windows"), \
             patch("install.Path.home", return_value=Path("C:/Users/TestUser")):
            result = install.install_hooks()

        assert result == "Hooks: updated stop hook in settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        actual_cmd = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "~" not in actual_cmd
        assert "C:/Users/TestUser/.claude" in actual_cmd

    def test_already_installed_skips(self, tmp_path):
        """Installer should skip if hook command already matches."""
        settings_path = tmp_path / "settings.json"
        cmd = "python ~/.claude/skills/context-memory/scripts/auto_save.py"
        self._write_settings(settings_path, cmd)

        with patch.object(install, "SETTINGS_PATH", settings_path), \
             patch("install.platform.system", return_value="Linux"):
            result = install.install_hooks()

        assert result == "Hooks: already installed"

    def test_fresh_install_on_windows_expands_tilde(self, tmp_path):
        """Fresh install on Windows should write expanded path."""
        settings_path = tmp_path / "settings.json"
        # No existing settings file

        with patch.object(install, "SETTINGS_PATH", settings_path), \
             patch("install.platform.system", return_value="Windows"), \
             patch("install.Path.home", return_value=Path("C:/Users/TestUser")):
            result = install.install_hooks()

        assert result == "Hooks: stop hook added to settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        actual_cmd = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "~" not in actual_cmd
        assert "C:/Users/TestUser/.claude" in actual_cmd


class TestInstallMcp:
    def test_writes_mcp_servers_json(self, tmp_path):
        """install_mcp() should write directly to mcp_servers.json."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_path = claude_dir / "mcp_servers.json"
        # Create a fake server script so the path resolves
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        server_script = scripts_dir / "mcp_server.py"
        server_script.write_text("# fake", encoding="utf-8")

        with patch.object(install, "CLAUDE_DIR", claude_dir), \
             patch.object(install, "SKILL_DST", tmp_path), \
             patch.object(install, "MCP_SERVER_SCRIPT", server_script), \
             patch("subprocess.run"):  # mcp import check
            result = install.install_mcp()

        assert result == "MCP server: registered in mcp_servers.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert "context-memory" in config
        assert config["context-memory"]["command"] == sys.executable
        assert "cwd" in config["context-memory"]

    def test_preserves_existing_entries(self, tmp_path):
        """install_mcp() should not overwrite other MCP server entries."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_path = claude_dir / "mcp_servers.json"
        config_path.write_text(json.dumps({"other-server": {"command": "node"}}), encoding="utf-8")
        server_script = tmp_path / "scripts" / "mcp_server.py"
        server_script.parent.mkdir()
        server_script.write_text("# fake", encoding="utf-8")

        with patch.object(install, "CLAUDE_DIR", claude_dir), \
             patch.object(install, "SKILL_DST", tmp_path), \
             patch.object(install, "MCP_SERVER_SCRIPT", server_script), \
             patch("subprocess.run"):
            install.install_mcp()

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert "other-server" in config
        assert "context-memory" in config

    def test_skips_when_mcp_not_installed(self, tmp_path):
        """install_mcp() should skip gracefully when mcp package is missing."""
        with patch.object(install, "CLAUDE_DIR", tmp_path), \
             patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "python")):
            result = install.install_mcp()

        assert "not installed" in result
