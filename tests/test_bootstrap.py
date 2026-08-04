from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts/init_plugin.py"


class BootstrapTests(unittest.TestCase):
    def command(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INIT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_dry_run_does_not_write_and_normalizes_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "new-plugin"
            result = self.command(
                "--target", str(target), "--dry-run", "--name", "My Plugin",
                "--description", "A plugin", "--repository", "https://github.com/acme/my-plugin",
                "--author-name", "Acme", "--npm-scope", "@acme",
                "--npm-package", "@acme/my-plugin", "--skill-name", "First Skill",
                "--skill-description", "Run the first skill.",
            )
            self.assertIn('"name": "my-plugin"', result.stdout)
            self.assertFalse(target.exists())

    def test_generation_is_checkable_and_collision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "generated"
            arguments = (
                "--target", str(target), "--name", "test-plugin", "--description", "A test plugin",
                "--repository", "https://github.com/acme/test-plugin", "--author-name", "Acme",
                "--npm-scope", "@acme", "--npm-package", "@acme/test-plugin", "--skill-name", "test",
                "--skill-description", "Run the test skill.",
            )
            self.command(*arguments)
            installers = (
                "install-codex.sh", "install-codex.ps1",
                "install-claude-code.sh", "install-claude-code.ps1",
                "install-opencode.sh", "install-opencode.ps1",
            )
            for installer in installers:
                self.assertTrue((target / "scripts/install" / installer).is_file())
                self.assertFalse((target / installer).exists())
            checked = subprocess.run(
                [sys.executable, str(target / "tooling/plugin.py"), "check"],
                cwd=target,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("deterministic assembly", checked.stdout)
            before = (target / "README.md").read_bytes()
            collision = self.command(*arguments, check=False)
            self.assertNotEqual(collision.returncode, 0)
            self.assertIn("existing generated files", collision.stderr)
            self.assertEqual(before, (target / "README.md").read_bytes())

    def test_config_file_and_flag_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            config = {
                "schemaVersion": 1,
                "plugin": {
                    "name": "config-plugin",
                    "description": "From config",
                    "repository": "https://github.com/acme/config-plugin",
                    "author": {"name": "Config Author"},
                    "npm": {"scope": "@acme", "package": "@acme/config-plugin"},
                    "skills": [{"name": "config", "description": "Config skill."}],
                },
            }
            config_path = temp_path / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = self.command(
                "--target", str(temp_path / "target"), "--config", str(config_path),
                "--description", "From flag",
                "--dry-run",
            )
            self.assertIn('"description": "From flag"', result.stdout)
            self.assertIn('"name": "config-plugin"', result.stdout)

    def test_sync_regenerates_installers_before_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "generated"
            self.command(
                "--target", str(target), "--name", "test-plugin", "--description", "A test plugin",
                "--repository", "https://github.com/acme/test-plugin", "--author-name", "Acme",
                "--npm-scope", "@acme", "--npm-package", "@acme/test-plugin", "--skill-name", "test",
                "--skill-description", "Run the test skill.",
            )
            config_path = target / "plugin.config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["plugin"]["name"] = "renamed-plugin"
            config["plugin"]["repository"] = "https://github.com/acme/renamed-plugin"
            config["plugin"]["npm"]["package"] = "@acme/renamed-plugin"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(target / "tooling/plugin.py"), "sync-publication"],
                cwd=target,
                text=True,
                capture_output=True,
                check=True,
            )
            checked = subprocess.run(
                [sys.executable, str(target / "tooling/plugin.py"), "check"],
                cwd=target,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("deterministic assembly", checked.stdout)


if __name__ == "__main__":
    unittest.main()
