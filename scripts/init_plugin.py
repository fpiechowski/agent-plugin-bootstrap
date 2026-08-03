#!/usr/bin/env python3
"""Non-interactive, collision-safe generator for new agent plugin repositories."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REPOSITORY_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$")
NPM_SCOPE_RE = re.compile(r"^@[a-z0-9][a-z0-9._-]*$")
NPM_PACKAGE_RE = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")


class InitError(ValueError):
    """A readable user-facing initialization error."""


def nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InitError(f"{field}: a non-empty value is required")
    return value.strip()


def slugify(value: Any, field: str) -> str:
    text = nonempty(value, field).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text or not NAME_RE.fullmatch(text) or len(text) > 64:
        raise InitError(f"{field}: cannot be normalized to a kebab-case name")
    return text


def title_for(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("-"))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InitError(f"cannot read config {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InitError(f"config {path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InitError("config: root must be an object")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a production-ready agent plugin repository")
    parser.add_argument("--target", required=True, help="directory to create")
    parser.add_argument("--config", help="JSON file containing generator metadata")
    parser.add_argument("--version", help="initial SemVer (default: 0.1.0)")
    parser.add_argument("--dry-run", action="store_true", help="print the normalized plan without writing")
    parser.add_argument("--name")
    parser.add_argument("--display-name")
    parser.add_argument("--description")
    parser.add_argument("--long-description")
    parser.add_argument("--repository")
    parser.add_argument("--license")
    parser.add_argument("--category")
    parser.add_argument("--brand-color")
    parser.add_argument("--author-name")
    parser.add_argument("--author-url")
    parser.add_argument("--author-email")
    parser.add_argument("--npm-scope")
    parser.add_argument("--npm-package")
    parser.add_argument("--skill-name")
    parser.add_argument("--skill-display-name")
    parser.add_argument("--skill-description")
    parser.add_argument("--invocation", choices=("explicit", "implicit"))
    return parser.parse_args(argv)


def load_spec(args: argparse.Namespace) -> dict[str, Any]:
    raw = read_json(Path(args.config).resolve()) if args.config else {}
    source = dict(raw.get("plugin", raw))
    if "schemaVersion" in raw and raw["schemaVersion"] != 1:
        raise InitError("config.schemaVersion: expected 1")

    overrides = {
        "name": args.name,
        "displayName": args.display_name,
        "description": args.description,
        "longDescription": args.long_description,
        "repository": args.repository,
        "license": args.license,
        "category": args.category,
        "brandColor": args.brand_color,
    }
    for key, value in overrides.items():
        if value is not None:
            source[key] = value

    name = slugify(source.get("name"), "plugin.name")
    version_value = args.version or raw.get("version", source.get("version", "0.1.0"))
    if not isinstance(version_value, str) or not SEMVER_RE.fullmatch(version_value.strip()):
        raise InitError("version: expected a valid SemVer value")
    version_value = version_value.strip()
    display_name = nonempty(source.get("displayName", title_for(name)), "plugin.displayName")
    description = nonempty(source.get("description"), "plugin.description")
    long_description = nonempty(source.get("longDescription", description), "plugin.longDescription")
    repository = nonempty(source.get("repository"), "plugin.repository")
    if not REPOSITORY_RE.fullmatch(repository):
        raise InitError("plugin.repository: expected https://github.com/owner/repository")
    license_name = nonempty(source.get("license", "MIT"), "plugin.license")
    category = nonempty(source.get("category", "Developer Tools"), "plugin.category")
    brand_color = nonempty(source.get("brandColor", "#0F172A"), "plugin.brandColor")

    author_source = dict(source.get("author", {}))
    for key, value in (("name", args.author_name), ("url", args.author_url), ("email", args.author_email)):
        if value is not None:
            author_source[key] = value
    author = {"name": nonempty(author_source.get("name"), "plugin.author.name")}
    for key in ("url", "email"):
        if author_source.get(key) is not None:
            author[key] = nonempty(author_source[key], f"plugin.author.{key}")

    npm_source = dict(source.get("npm", {}))
    if args.npm_scope is not None:
        npm_source["scope"] = args.npm_scope
    if args.npm_package is not None:
        npm_source["package"] = args.npm_package
    npm_scope = nonempty(npm_source.get("scope"), "plugin.npm.scope")
    npm_package = nonempty(npm_source.get("package"), "plugin.npm.package")
    if not NPM_SCOPE_RE.fullmatch(npm_scope):
        raise InitError("plugin.npm.scope: expected an npm scope such as @acme")
    if not NPM_PACKAGE_RE.fullmatch(npm_package) or not npm_package.startswith(npm_scope + "/"):
        raise InitError("plugin.npm.package: expected a package belonging to plugin.npm.scope")

    configured_skills = source.get("skills")
    if configured_skills is None:
        configured_skills = [{}]
    if not isinstance(configured_skills, list) or not configured_skills:
        raise InitError("plugin.skills: provide at least one skill")
    skills: list[dict[str, Any]] = []
    for index, configured in enumerate(configured_skills):
        if not isinstance(configured, dict):
            raise InitError(f"plugin.skills[{index}]: expected an object")
        item = dict(configured)
        if index == 0:
            if args.skill_name is not None:
                item["name"] = args.skill_name
            if args.skill_display_name is not None:
                item["displayName"] = args.skill_display_name
            if args.skill_description is not None:
                item["description"] = args.skill_description
            if args.invocation is not None:
                item["invocation"] = args.invocation
        skill_name = slugify(item.get("name", name), f"plugin.skills[{index}].name")
        skill_description = nonempty(item.get("description"), f"plugin.skills[{index}].description")
        skill = {
            "name": skill_name,
            "displayName": nonempty(item.get("displayName", title_for(skill_name)), f"plugin.skills[{index}].displayName"),
            "description": skill_description,
            "invocation": item.get("invocation", "explicit"),
            "source": f"core/skills/{skill_name}",
        }
        if skill["invocation"] not in {"explicit", "implicit"}:
            raise InitError(f"plugin.skills[{index}].invocation: expected explicit or implicit")
        skills.append(skill)
    if len({skill["name"] for skill in skills}) != len(skills):
        raise InitError("plugin.skills: skill names must be unique after normalization")

    return {
        "schemaVersion": 1,
        "version": version_value,
        "plugin": {
            "name": name,
            "displayName": display_name,
            "description": description,
            "longDescription": long_description,
            "category": category,
            "license": license_name,
            "repository": repository,
            "homepage": source.get("homepage", repository),
            "keywords": list(source.get("keywords", [])),
            "author": author,
            "npm": {"scope": npm_scope, "package": npm_package, "access": "public"},
            "brandColor": brand_color,
            "skills": skills,
            "hosts": source.get("hosts", raw.get("hosts", {"codex": {}, "claude-code": {}, "opencode": {}})),
        },
    }


def skill_content(skill: dict[str, Any], plugin: dict[str, Any]) -> str:
    template_path = PACKAGE_ROOT / "templates/starter-skill.md.tmpl"
    if template_path.is_file():
        template = template_path.read_text(encoding="utf-8")
        return (template.replace("{{SKILL_NAME}}", skill["name"])
                .replace("{{SKILL_DESCRIPTION}}", json.dumps(skill["description"]))
                .replace("{{PLUGIN_DISPLAY_NAME}}", plugin["displayName"]))
    raise InitError(f"missing starter skill template: {template_path}")


def root_readme(spec: dict[str, Any]) -> str:
    plugin = spec["plugin"]
    name = plugin["name"]
    return f"""# {plugin['displayName']}

{plugin['longDescription']}

This repository uses one canonical skill core and generated Codex, Claude Code, and OpenCode distributions.

## Development

```text
python tooling/plugin.py check
python tooling/plugin.py assemble
python tooling/plugin.py sync-publication
python tooling/plugin.py package-release
```

The canonical sources live under `core/skills/` and host-specific extensions under `adapters/`.
`VERSION` is the single release version. Edit source files, then run `sync-publication` so committed
distributions, marketplaces, and installers stay reproducible.

## Invocation

- Codex: `${name}`
- Claude Code: `/{name}:{name}`
- OpenCode: `/{name}`

Generated one-line installers are available at the repository root after publication sync.
"""


def agents_md(spec: dict[str, Any]) -> str:
    return f"""# Agent instructions

- Treat `core/` and `adapters/` as canonical sources; do not hand-edit `dist/`.
- Run `python tooling/plugin.py check` after source changes.
- Run `python tooling/plugin.py sync-publication` before committing generated artifacts.
- Keep all published paths relative to the distribution root.
- Release only from a `v<SemVer>` tag matching `VERSION`.

The generated plugin is `{spec['plugin']['name']}`.
"""


def workflow_files() -> dict[str, str]:
    token_expression = "$" + "{{ github.token }}"
    check = """name: Check
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python tooling/plugin.py check
      - run: python tooling/plugin.py assemble --output build/ci-assembly
      - run: node --check build/ci-assembly/publication/dist/opencode/.opencode/plugins/*.js
"""
    release = f"""name: Release
on:
  push:
    tags: ['v*.*.*']
permissions:
  contents: write
  id-token: write
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: https://registry.npmjs.org
      - name: Verify tag and source
        shell: bash
        run: |
          version="$(tr -d '\\r\\n' < VERSION)"
          test "v$version" = "$GITHUB_REF_NAME"
          python tooling/plugin.py check
      - name: Build release assets
        run: python tooling/plugin.py package-release
      - name: Create GitHub release
        env:
          GH_TOKEN: {token_expression}
        run: gh release create "$GITHUB_REF_NAME" build/release/* --verify-tag --generate-notes
      - name: Publish OpenCode npm package
        run: npm publish --provenance --access public
        working-directory: dist/opencode
"""
    return {".github/workflows/check.yml": check, ".github/workflows/release.yml": release}


def copy_source_tree(staging: Path, spec: dict[str, Any]) -> None:
    plugin = spec["plugin"]
    write_text(staging / "VERSION", spec["version"])
    write_json(staging / "plugin.config.json", spec)
    write_text(staging / "README.md", root_readme(spec))
    write_text(staging / "AGENTS.md", agents_md(spec))
    write_text(staging / "LICENSE", "MIT License\n\nCopyright (c) 2026 Filip Piechowski\n")
    write_text(staging / ".gitignore", "__pycache__/\nbuild/\n*.pyc\n")
    for skill in plugin["skills"]:
        write_text(staging / skill["source"] / "SKILL.md", skill_content(skill, plugin))
    for relative in ("adapters", "templates"):
        source = PACKAGE_ROOT / relative
        if source.is_dir():
            copy_tree(source, staging / relative)
    for host in ("codex", "claude-code", "opencode"):
        components = staging / "adapters" / host / "components"
        components.mkdir(parents=True, exist_ok=True)
        write_text(components / ".gitkeep", "")
    tooling_source = PACKAGE_ROOT / "tooling/plugin.py"
    staging_tooling = staging / "tooling/plugin.py"
    staging_tooling.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tooling_source, staging_tooling)
    for relative, content in workflow_files().items():
        write_text(staging / relative, content)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\r\n", "\n").rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def copy_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file() and not path.is_symlink():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def load_assembler(staging: Path):
    spec = importlib.util.spec_from_file_location("generated_plugin_tooling", staging / "tooling/plugin.py")
    if spec is None or spec.loader is None:
        raise InitError("generated tooling could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def planned_files(staging: Path) -> list[str]:
    return [path.relative_to(staging).as_posix() for path in sorted(staging.rglob("*")) if path.is_file()]


def generate(args: argparse.Namespace) -> None:
    spec = load_spec(args)
    target_input = Path(args.target).expanduser()
    if target_input.is_symlink():
        raise InitError("target must not be a symbolic link")
    target = target_input.resolve()
    if target.exists() and not target.is_dir():
        raise InitError(f"target is not a directory: {target}")
    with tempfile.TemporaryDirectory(prefix="agent-plugin-init-") as temp:
        staging = Path(temp) / "repo"
        copy_source_tree(staging, spec)
        assembler = load_assembler(staging)
        assembler.sync_publication(staging)
        shutil.rmtree(staging / "tooling/__pycache__", ignore_errors=True)
        files = planned_files(staging)
        if args.dry_run:
            print(json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True))
            print("\nPlanned files:")
            print("\n".join(files))
            return
        target.mkdir(parents=True, exist_ok=True)
        collisions = [relative for relative in files if (target / relative).exists()]
        if collisions:
            preview = ", ".join(collisions[:8])
            suffix = " ..." if len(collisions) > 8 else ""
            raise InitError(f"target contains existing generated files: {preview}{suffix}; no files were changed")
        for relative in files:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / relative, destination)
    print(f"Initialized {spec['plugin']['name']} at {target}")


def main(argv: list[str] | None = None) -> int:
    try:
        generate(parse_args(argv))
    except (InitError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
