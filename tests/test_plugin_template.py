from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tooling/plugin.py"


class PluginTemplateTests(unittest.TestCase):
    def temporary_output(self) -> tempfile.TemporaryDirectory[str]:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=build_root)

    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_source_and_publication_are_checkable(self) -> None:
        result = self.command("check")
        self.assertIn("deterministic assembly", result.stdout)

    def test_assembly_has_three_hosts_without_marketplaces(self) -> None:
        with self.temporary_output() as temp:
            output = Path(temp) / "assembly"
            self.command("assemble", "--output", str(output))
            publication = output / "publication"
            self.assertTrue((publication / "dist/codex/.codex-plugin/plugin.json").is_file())
            self.assertTrue((publication / "dist/claude-code/.claude-plugin/plugin.json").is_file())
            self.assertTrue((publication / "dist/opencode/package.json").is_file())
            self.assertFalse((publication / ".agents").exists())
            self.assertFalse((publication / ".claude-plugin/marketplace.json").exists())

            codex = json.loads((publication / "dist/codex/.codex-plugin/plugin.json").read_text())
            self.assertEqual(codex["name"], "my-plugin")
            self.assertTrue((publication / "dist/codex/skills/my-plugin/agents/openai.yaml").is_file())

    def test_generated_packages_do_not_include_bootstrap_sources(self) -> None:
        with self.temporary_output() as temp:
            output = Path(temp) / "assembly"
            self.command("assemble", "--output", str(output))
            for package in (output / "publication").glob("dist/*"):
                paths = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
                self.assertFalse(any(path.startswith(("scripts/", "templates/", "tooling/", "adapters/")) for path in paths))


if __name__ == "__main__":
    unittest.main()
