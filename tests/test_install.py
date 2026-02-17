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


class TestInstallCommands:
    def test_fresh_install(self, tmp_path):
        """Command files should be installed when destination doesn't exist."""
        src = tmp_path / "src_commands"
        src.mkdir()
        (src / "remember.md").write_text("# remember", encoding="utf-8")
        (src / "recall.md").write_text("# recall", encoding="utf-8")

        dst = tmp_path / "commands"
        dst.mkdir()

        with patch.object(install, "COMMANDS_SRC", src), \
             patch.object(install, "COMMANDS_DST", dst):
            result = install.install_commands()

        assert "remember.md: installed" in result
        assert "recall.md: installed" in result
        assert (dst / "remember.md").read_text(encoding="utf-8") == "# remember"
        assert (dst / "recall.md").read_text(encoding="utf-8") == "# recall"

    def test_already_up_to_date(self, tmp_path):
        """Identical files should be reported as up to date."""
        src = tmp_path / "src_commands"
        src.mkdir()
        (src / "remember.md").write_text("# same content", encoding="utf-8")
        (src / "recall.md").write_text("# recall content", encoding="utf-8")

        dst = tmp_path / "commands"
        dst.mkdir()
        (dst / "remember.md").write_text("# same content", encoding="utf-8")
        (dst / "recall.md").write_text("# recall content", encoding="utf-8")

        with patch.object(install, "COMMANDS_SRC", src), \
             patch.object(install, "COMMANDS_DST", dst):
            result = install.install_commands()

        assert "already up to date" in result

    def test_creates_backup_on_update(self, tmp_path):
        """Changed files should be backed up before overwriting."""
        src = tmp_path / "src_commands"
        src.mkdir()
        (src / "remember.md").write_text("# new version", encoding="utf-8")

        dst = tmp_path / "commands"
        dst.mkdir()
        (dst / "remember.md").write_text("# old version", encoding="utf-8")

        with patch.object(install, "COMMANDS_SRC", src), \
             patch.object(install, "COMMANDS_DST", dst):
            result = install.install_commands()

        assert "updated" in result
        assert "backup" in result
        assert (dst / "remember.md").read_text(encoding="utf-8") == "# new version"
        assert (dst / "remember.md.bak").exists()
        assert (dst / "remember.md.bak").read_text(encoding="utf-8") == "# old version"

    def test_source_not_found(self, tmp_path):
        """Missing source files should be skipped gracefully."""
        src = tmp_path / "src_commands"
        src.mkdir()
        # Only create one of the two expected files

        dst = tmp_path / "commands"
        dst.mkdir()

        with patch.object(install, "COMMANDS_SRC", src), \
             patch.object(install, "COMMANDS_DST", dst):
            result = install.install_commands()

        assert "source not found" in result


class TestInstallDb:
    def test_skips_existing_db(self, tmp_path):
        """install_db() should skip when database already exists."""
        db_dir = tmp_path / "context-memory"
        db_dir.mkdir()
        (db_dir / "context.db").write_bytes(b"fake db")

        with patch.object(install, "DB_DIR", db_dir):
            result = install.install_db()

        assert result == "Database: already exists"

    def test_init_success(self, tmp_path):
        """install_db() should report success when db_init.py succeeds."""
        db_dir = tmp_path / "context-memory"
        db_dir.mkdir()

        with patch.object(install, "DB_DIR", db_dir), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = install.install_db()

        assert result == "Database: initialized"

    def test_init_failure(self, tmp_path):
        """install_db() should report failure when db_init.py fails."""
        db_dir = tmp_path / "context-memory"
        db_dir.mkdir()

        with patch.object(install, "DB_DIR", db_dir), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Schema error"
            )
            result = install.install_db()

        assert "init failed" in result
        assert "Schema error" in result


class TestInstallSkill:
    def test_copies_skill_directory(self, tmp_path):
        """install_skill() should copy the skill directory to the destination."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# Skill", encoding="utf-8")
        scripts = src / "scripts"
        scripts.mkdir()
        (scripts / "db_init.py").write_text("# init", encoding="utf-8")

        dst = tmp_path / "dst" / "skills" / "context-memory"

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=False)

        assert result == "Skill copied"
        assert dst.exists()
        assert (dst / "SKILL.md").exists()
        assert (dst / "scripts" / "db_init.py").exists()

    def test_creates_parent_directories(self, tmp_path):
        """install_skill() should create parent dirs if they don't exist."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# Skill", encoding="utf-8")

        dst = tmp_path / "deep" / "nested" / "skills" / "context-memory"

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=False)

        assert result == "Skill copied"
        assert dst.exists()

    def test_overwrites_existing_directory(self, tmp_path):
        """install_skill() should remove and replace an existing skill directory."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# New version", encoding="utf-8")

        dst = tmp_path / "dst" / "skills" / "context-memory"
        dst.mkdir(parents=True)
        (dst / "SKILL.md").write_text("# Old version", encoding="utf-8")
        (dst / "stale_file.txt").write_text("should be removed", encoding="utf-8")

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=False)

        assert result == "Skill copied"
        assert (dst / "SKILL.md").read_text(encoding="utf-8") == "# New version"
        assert not (dst / "stale_file.txt").exists()

    def test_symlink_mode(self, tmp_path):
        """install_skill(symlink=True) should create a symlink."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# Skill", encoding="utf-8")

        dst = tmp_path / "dst" / "skills" / "context-memory"

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=True)

        assert result == "Skill symlinked"
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_symlink_replaces_existing_symlink(self, tmp_path):
        """install_skill(symlink=True) should replace an existing symlink."""
        old_target = tmp_path / "old_target"
        old_target.mkdir()

        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)

        dst = tmp_path / "dst" / "skills" / "context-memory"
        dst.parent.mkdir(parents=True)
        dst.symlink_to(old_target, target_is_directory=True)

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=True)

        assert result == "Skill symlinked"
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_symlink_replaces_existing_directory(self, tmp_path):
        """install_skill(symlink=True) should remove an existing directory and create symlink."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)

        dst = tmp_path / "dst" / "skills" / "context-memory"
        dst.mkdir(parents=True)
        (dst / "old_file.txt").write_text("old", encoding="utf-8")

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            result = install.install_skill(symlink=True)

        assert result == "Skill symlinked"
        assert dst.is_symlink()

    def test_ignores_pycache(self, tmp_path):
        """install_skill() should not copy __pycache__ or .pyc files."""
        src = tmp_path / "src" / "skills" / "context-memory"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# Skill", encoding="utf-8")
        pycache = src / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-311.pyc").write_bytes(b"\x00")
        (src / "old.pyc").write_bytes(b"\x00")

        dst = tmp_path / "dst" / "skills" / "context-memory"

        with patch.object(install, "SKILL_SRC", src), \
             patch.object(install, "SKILL_DST", dst):
            install.install_skill(symlink=False)

        assert (dst / "SKILL.md").exists()
        assert not (dst / "__pycache__").exists()
        assert not (dst / "old.pyc").exists()
