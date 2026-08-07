#!/usr/bin/env python3
"""Deterministic assembler, validator, and release packager for agent plugins."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
NPM_SCOPE_RE = re.compile(r"^@[a-z0-9][a-z0-9._-]*$")
NPM_PACKAGE_RE = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")


class ValidationError(RuntimeError):
    """Raised when source or generated publication violates the contract."""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\r\n", "\n").rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def valid_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise ValidationError(f"{field}: expected lower-case kebab-case name")
    if len(value) > 64:
        raise ValidationError(f"{field}: name is limited to 64 characters")
    return value


def require_string(value: Any, field: str, *, max_length: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field}: expected a non-empty string")
    result = value.strip()
    if max_length and len(result) > max_length:
        raise ValidationError(f"{field}: must be at most {max_length} characters")
    return result


def resolve_inside(root: Path, relative: str, field: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"{field}: path escapes the repository: {relative}") from exc
    return path


def github_repository(value: str) -> tuple[str, str]:
    match = URL_RE.fullmatch(value)
    if not match:
        raise ValidationError("plugin.repository: expected https://github.com/owner/repository")
    return match.group(1), match.group(2)


def load_config(root: Path = ROOT) -> dict[str, Any]:
    path = root / "plugin.config.json"
    config = read_json(path)
    if config.get("schemaVersion") != 1:
        raise ValidationError(f"{path}: schemaVersion must be 1")
    plugin = config.get("plugin")
    if not isinstance(plugin, dict):
        raise ValidationError(f"{path}: plugin must be an object")
    valid_name(plugin.get("name"), "plugin.name")
    for field in ("displayName", "description", "category", "license", "repository"):
        require_string(plugin.get(field), f"plugin.{field}")
    require_string(plugin.get("longDescription", plugin.get("description")), "plugin.longDescription")
    github_repository(plugin["repository"])
    author = plugin.get("author")
    if not isinstance(author, dict):
        raise ValidationError("plugin.author: expected an object")
    require_string(author.get("name"), "plugin.author.name")
    if "email" in author:
        require_string(author["email"], "plugin.author.email")
    if "url" in author:
        require_string(author["url"], "plugin.author.url")
    npm = plugin.get("npm")
    if not isinstance(npm, dict):
        raise ValidationError("plugin.npm: expected an object")
    scope = require_string(npm.get("scope"), "plugin.npm.scope")
    package = require_string(npm.get("package"), "plugin.npm.package")
    if not NPM_SCOPE_RE.fullmatch(scope):
        raise ValidationError("plugin.npm.scope: expected an npm scope such as @acme")
    if not NPM_PACKAGE_RE.fullmatch(package):
        raise ValidationError("plugin.npm.package: invalid npm package name")
    if not package.startswith(scope + "/"):
        raise ValidationError("plugin.npm.package: package must belong to plugin.npm.scope")
    if npm.get("access", "public") != "public":
        raise ValidationError("plugin.npm.access: only public packages are supported")
    skills = plugin.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValidationError("plugin.skills: at least one skill is required")
    seen: set[str] = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            raise ValidationError(f"plugin.skills[{index}]: expected an object")
        name = valid_name(skill.get("name"), f"plugin.skills[{index}].name")
        if name in seen:
            raise ValidationError(f"plugin.skills: duplicate skill {name!r}")
        seen.add(name)
        require_string(skill.get("displayName", name), f"plugin.skills[{index}].displayName")
        require_string(skill.get("description"), f"plugin.skills[{index}].description", max_length=1024)
        invocation = skill.get("invocation", "explicit")
        if invocation not in {"explicit", "implicit"}:
            raise ValidationError(f"plugin.skills[{index}].invocation: expected explicit or implicit")
        source = skill.get("source", f"core/skills/{name}")
        if not isinstance(source, str):
            raise ValidationError(f"plugin.skills[{index}].source: expected a relative path")
        source_path = resolve_inside(root, source, f"plugin.skills[{index}].source")
        if not source_path.is_dir():
            raise ValidationError(f"plugin.skills[{index}].source: directory does not exist: {source}")
    return config


def version(root: Path = ROOT) -> str:
    value = read_text(root / "VERSION").strip()
    if not SEMVER_RE.fullmatch(value):
        raise ValidationError(f"VERSION: invalid SemVer {value!r}")
    return value


def parse_frontmatter(content: str, path: Path) -> tuple[dict[str, str], str]:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValidationError(f"{path}: missing opening YAML frontmatter")
    closing = normalized.find("\n---\n", 4)
    if closing < 0:
        raise ValidationError(f"{path}: missing closing YAML frontmatter")
    metadata: dict[str, str] = {}
    for line in normalized[4:closing].splitlines():
        if not line.strip():
            continue
        if ":" not in line or line.startswith(" "):
            raise ValidationError(f"{path}: only scalar frontmatter fields are supported")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9-]*", key) or key in metadata:
            raise ValidationError(f"{path}: invalid or duplicate frontmatter key {key!r}")
        metadata[key] = value.strip().strip('"').strip("'")
    body = normalized[closing + 5 :].lstrip("\n").rstrip("\n") + "\n"
    return metadata, body


def materialize_skill(root: Path, skill: dict[str, Any], host: str) -> tuple[dict[str, str], str, dict[str, str]]:
    name = skill["name"]
    source = resolve_inside(root, skill.get("source", f"core/skills/{name}"), f"skill {name}.source")
    manifest_path = source / "SKILL.md"
    canonical = read_text(manifest_path)
    metadata, body = parse_frontmatter(canonical, manifest_path)
    if metadata.get("name") != name:
        raise ValidationError(f"{manifest_path}: frontmatter name must be {name}")
    if metadata.get("description") != skill["description"]:
        raise ValidationError(f"{manifest_path}: description differs from plugin.config.json")
    files: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.name != "SKILL.md":
            files[path.relative_to(source).as_posix()] = read_text(path)
    references: dict[str, str] = {relative: content for relative, content in files.items() if relative.endswith(".md")}
    for shared_relative in skill.get("shared", []):
        if not isinstance(shared_relative, str) or Path(shared_relative).name != shared_relative:
            raise ValidationError(f"skill {name}.shared: expected a file name")
        shared_path = resolve_inside(root, f"core/shared/{shared_relative}", f"skill {name}.shared")
        if not shared_path.is_file():
            raise ValidationError(f"{shared_path}: shared file does not exist")
        target = f"references/{shared_relative}"
        files[target] = read_text(shared_path)
        references[target] = files[target]
        body = body.replace(f"../shared/{shared_relative}", target)
    runtime = "---\nname: " + name + "\ndescription: " + json.dumps(skill["description"]) + "\n"
    if host == "claude-code" and skill.get("invocation", "explicit") == "explicit":
        runtime += "disable-model-invocation: true\n"
    if host == "opencode" and skill.get("invocation", "explicit") == "explicit":
        runtime += 'metadata:\n  opencode/autoinvoke: "false"\n'
    files["SKILL.md"] = runtime + "---\n\n" + body
    return files, body, references


def write_files(destination: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        if relative.startswith("../") or "\\" in relative:
            raise ValidationError(f"generated path escapes package: {relative}")
        write_text(destination / relative, content)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise ValidationError(f"symlinks are not allowed in published components: {path}")
        if path.is_file() and path.name != ".gitkeep" and path.suffix != ".pyc":
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def plugin_info(config: dict[str, Any]) -> dict[str, Any]:
    return config["plugin"]


def open_code_contract(body: str, references: dict[str, str]) -> str:
    modules = "\n\n".join(f"## Loaded module: {relative}\n\n{content.rstrip()}" for relative, content in sorted(references.items()))
    return body.rstrip() + ("\n\n# Loaded modules\n\n" + modules if modules else "") + "\n"


def component_root(root: Path, host: str) -> Path:
    return root / "adapters" / host / "components"


def copy_host_components(root: Path, host: str, destination: Path) -> None:
    copy_tree(component_root(root, host), destination)


def read_optional_object(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def codex_manifest(config: dict[str, Any], ver: str, root: Path) -> dict[str, Any]:
    info = plugin_info(config)
    author = dict(info["author"])
    manifest: dict[str, Any] = {
        "name": info["name"], "version": ver, "description": info["description"],
        "author": author, "homepage": info.get("homepage", info["repository"]),
        "repository": info["repository"], "license": info["license"],
        "keywords": info.get("keywords", []), "skills": "./skills/",
        "interface": {
            "displayName": info["displayName"], "shortDescription": info["description"],
            "longDescription": info.get("longDescription", info["description"]),
            "developerName": author["name"], "category": info["category"],
            "capabilities": ["Interactive"],
            "defaultPrompt": [skill.get("defaultPrompt", "Use $" + skill["name"] + " for this task.") for skill in info["skills"][:3]],
            "brandColor": info.get("brandColor", "#0F172A"),
        },
    }
    asset_dir = root / "adapters/codex/assets"
    icon = next(iter(sorted(asset_dir.glob("*.svg"))), None) if asset_dir.is_dir() else None
    if icon:
        manifest["interface"]["composerIcon"] = f"./assets/{icon.name}"
        manifest["interface"]["logo"] = f"./assets/{icon.name}"
    components = component_root(root, "codex")
    if (components / ".mcp.json").is_file():
        manifest["mcpServers"] = "./.mcp.json"
    if (components / ".app.json").is_file():
        manifest["apps"] = "./.app.json"
    return manifest


def claude_manifest(config: dict[str, Any], ver: str, root: Path) -> dict[str, Any]:
    info = plugin_info(config)
    manifest: dict[str, Any] = {
        "name": info["name"], "version": ver, "description": info["description"],
        "author": info["author"], "homepage": info.get("homepage", info["repository"]),
        "repository": info["repository"], "license": info["license"],
        "keywords": info.get("keywords", []), "skills": "./skills/",
    }
    components = component_root(root, "claude-code")
    for field, relative in (("commands", "commands"), ("agents", "agents"),
                            ("hooks", "hooks/hooks.json"), ("mcpServers", ".mcp.json"),
                            ("lspServers", ".lsp.json")):
        if (components / relative).exists():
            manifest[field] = f"./{relative}"
    return manifest


def opencode_plugin_source(name: str, version_value: str, commands: dict[str, dict[str, str]], mcp: dict[str, Any]) -> str:
    identifier = re.sub(r"[^A-Za-z0-9]", "_", name)
    payload = json.dumps(commands, ensure_ascii=False, sort_keys=True)
    mcp_payload = json.dumps(mcp, ensure_ascii=False, sort_keys=True)
    return f"""// Generated by tooling/plugin.py. Do not edit by hand.
const commands = {payload}
const mcp = {mcp_payload}

export const {identifier}Plugin = async () => ({{
  config: async (config) => {{
    config.command = {{ ...commands, ...(config.command ?? {{}}) }}
    if (Object.keys(mcp).length > 0) config.mcp = {{ ...mcp, ...(config.mcp ?? {{}}) }}
  }},
}})

export default {identifier}Plugin
// version: {version_value}
"""


def package_json(config: dict[str, Any], ver: str, files: list[str]) -> dict[str, Any]:
    info = plugin_info(config)
    return {
        "name": info["npm"]["package"], "version": ver, "description": info["description"],
        "type": "module", "exports": f"./.opencode/plugins/{info['name']}.js",
        "files": sorted(files), "license": info["license"], "private": False,
    }


def readme(config: dict[str, Any], ver: str) -> str:
    info = plugin_info(config)
    return f"""# {info['displayName']}

{info['longDescription']}

This package is generated from the repository's canonical core and adapter sources.

Version: {ver}
"""


def write_opencode_installer(destination: Path, config: dict[str, Any], ver: str) -> None:
    name = plugin_info(config)["name"]
    ps1 = f"""param([ValidateSet("Global", "Project")][string]$Scope = "Global", [string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Scope -eq "Global") {{ $configRoot = Join-Path $HOME ".config\\opencode" }} else {{ $configRoot = Join-Path (Resolve-Path $ProjectPath) ".opencode" }}
New-Item -ItemType Directory -Force -Path $configRoot | Out-Null
foreach ($folder in @('skills', 'commands', 'plugins')) {{ $source = Join-Path $sourceRoot ".opencode\\$folder"; $destination = Join-Path $configRoot $folder; if (Test-Path $source) {{ New-Item -ItemType Directory -Force -Path $destination | Out-Null; Get-ChildItem -Force $source | Copy-Item -Destination $destination -Recurse -Force }} }}
Write-Host "Installed {name} {ver} for OpenCode at $configRoot"
"""
    sh = f"""#!/usr/bin/env sh
set -eu
scope="global"; project_path="$(pwd)"
if [ "$#" -ge 1 ]; then scope="$1"; fi
if [ "$#" -ge 2 ]; then project_path="$2"; fi
source_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
case "$scope" in
  global) config_root="$HOME/.config/opencode" ;;
  project) config_root="$(CDPATH= cd -- "$project_path" && pwd)/.opencode" ;;
  *) echo "usage: sh ./install.sh [global|project] [project-path]" >&2; exit 2 ;;
esac
mkdir -p "$config_root"
for folder in skills commands plugins; do
  if [ -d "$source_root/.opencode/$folder" ]; then mkdir -p "$config_root/$folder"; cp -R "$source_root/.opencode/$folder"/. "$config_root/$folder"/; fi
done
echo "Installed {name} {ver} for OpenCode at $config_root"
"""
    write_text(destination / "install.ps1", ps1)
    write_text(destination / "install.sh", sh)


def render_release_installers(config: dict[str, Any], *, default_ref: str) -> dict[str, str]:
    owner, repo = github_repository(plugin_info(config)["repository"])
    name = plugin_info(config)["name"]
    asset = f"{name}-opencode.zip"
    sh = f"""#!/usr/bin/env sh
set -eu
scope="global"; project_path="$(pwd)"
if [ "$#" -ge 1 ]; then scope="$1"; fi
if [ "$#" -ge 2 ]; then project_path="$2"; fi
ref="{default_ref}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
archive="$tmp/{asset}"
url="https://github.com/{owner}/{repo}/releases/download/$ref/{asset}"
if command -v curl >/dev/null 2>&1; then curl -fsSL "$url" -o "$archive"; else wget -q "$url" -O "$archive"; fi
command -v unzip >/dev/null 2>&1 || {{ echo "unzip is required." >&2; exit 1; }}
unzip -q "$archive" -d "$tmp/dist"
sh "$tmp/dist/install.sh" "$scope" "$project_path"
"""
    ps1 = f"""param([ValidateSet("Global", "Project")][string]$Scope = "Global", [string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$tmp = Join-Path ([IO.Path]::GetTempPath()) "{name}-$([Guid]::NewGuid().ToString('N'))"
$archive = Join-Path $tmp "{asset}"
$extract = Join-Path $tmp "dist"
$url = "https://github.com/{owner}/{repo}/releases/download/{default_ref}/{asset}"
try {{ New-Item -ItemType Directory -Path $tmp | Out-Null; Invoke-WebRequest $url -OutFile $archive -UseBasicParsing; Expand-Archive -LiteralPath $archive -DestinationPath $extract; & (Join-Path $extract "install.ps1") -Scope $Scope -ProjectPath $ProjectPath }} finally {{ if (Test-Path $tmp) {{ [IO.Directory]::Delete($tmp, $true) }} }}
"""
    return {"install-opencode.sh": sh, "install-opencode.ps1": ps1}


def assemble(output: Path, root: Path = ROOT) -> None:
    config = load_config(root)
    ver = version(root)
    info = plugin_info(config)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    publication = output / "publication"
    codex_dist = publication / "dist/codex"
    claude_dist = publication / "dist/claude-code"
    open_dist = publication / "dist/opencode"
    codex_dist.mkdir(parents=True)
    claude_dist.mkdir(parents=True)
    open_dist.mkdir(parents=True)
    command_payload: dict[str, dict[str, str]] = {}
    integrity: dict[str, Any] = {"version": ver, "skills": {}}

    for skill in info["skills"]:
        name = skill["name"]
        codex_files, _, _ = materialize_skill(root, skill, "codex")
        claude_files, _, _ = materialize_skill(root, skill, "claude-code")
        open_files, open_body, open_refs = materialize_skill(root, skill, "opencode")
        write_files(codex_dist / "skills" / name, codex_files)
        write_files(claude_dist / "skills" / name, claude_files)
        write_files(open_dist / ".opencode/skills" / name, open_files)
        display = skill.get("displayName", name)
        contract = open_code_contract(open_body, open_refs)
        command_payload[name] = {"description": display, "template": contract}
        integrity["skills"][name] = {
            "codex": sha256_text("\0".join(codex_files[k] for k in sorted(codex_files))),
            "claude": sha256_text("\0".join(claude_files[k] for k in sorted(claude_files))),
            "opencode": sha256_text("\0".join(open_files[k] for k in sorted(open_files))),
        }
        allow = "true" if skill.get("invocation", "explicit") == "implicit" else "false"
        yaml = "interface:\n  display_name: " + json.dumps(display) + "\n"
        yaml += "  short_description: " + json.dumps(skill["description"]) + "\n"
        yaml += "  default_prompt: " + json.dumps(skill.get("defaultPrompt", "Use $" + name + ".")) + "\n"
        yaml += "policy:\n  allow_implicit_invocation: " + allow + "\n"
        write_text(codex_dist / "skills" / name / "agents/openai.yaml", yaml)
        write_text(open_dist / ".opencode/commands" / f"{name}.md", f"---\ndescription: {json.dumps(display)}\n---\n\n{contract}")

    copy_host_components(root, "codex", codex_dist)
    copy_host_components(root, "claude-code", claude_dist)
    copy_host_components(root, "opencode", open_dist)
    asset_dir = root / "adapters/codex/assets"
    if asset_dir.is_dir():
        copy_tree(asset_dir, codex_dist / "assets")
    write_json(codex_dist / ".codex-plugin/plugin.json", codex_manifest(config, ver, root))
    write_json(claude_dist / ".claude-plugin/plugin.json", claude_manifest(config, ver, root))
    mcp = read_optional_object(component_root(root, "opencode") / "mcp.json")
    write_text(open_dist / ".opencode/plugins" / f"{info['name']}.js", opencode_plugin_source(info["name"], ver, command_payload, mcp))
    write_text(open_dist / "README.md", readme(config, ver))
    write_text(open_dist / "VERSION", ver)
    write_opencode_installer(open_dist, config, ver)
    package_files = [p.relative_to(open_dist).as_posix() for p in open_dist.rglob("*") if p.is_file()]
    write_json(open_dist / "package.json", package_json(config, ver, package_files))
    write_json(output / "integrity.json", integrity)


def tree_snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def validate_package_no_external_paths(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
            continue
        content = read_text(path)
        if "](" + "../" in content or "](" + "..\\" in content:
            raise ValidationError(f"{path}: published artifact contains an external relative path")
        if re.search(r"\{\{\s*[A-Za-z_]", content):
            raise ValidationError(f"{path}: published artifact contains an unresolved template token")


def validate_assembly(output: Path, root: Path = ROOT) -> None:
    config = load_config(root)
    ver = version(root)
    info = plugin_info(config)
    publication = output / "publication"
    codex = publication / "dist/codex"
    claude = publication / "dist/claude-code"
    open_dist = publication / "dist/opencode"
    for path in (codex, claude, open_dist):
        if not path.exists():
            raise ValidationError(f"missing generated artifact: {path}")
    if (publication / ".agents").exists() or (publication / ".claude-plugin").exists():
        raise ValidationError("marketplace files must not be generated")
    codex_manifest = read_json(codex / ".codex-plugin/plugin.json")
    claude_manifest = read_json(claude / ".claude-plugin/plugin.json")
    for manifest, label in ((codex_manifest, "Codex"), (claude_manifest, "Claude Code")):
        if manifest.get("name") != info["name"] or manifest.get("version") != ver:
            raise ValidationError(f"{label} manifest does not match plugin.config.json/VERSION")
    if codex_manifest.get("skills") != "./skills/":
        raise ValidationError("Codex manifest must declare ./skills/")
    for skill in info["skills"]:
        name = skill["name"]
        for package in (codex / "skills" / name, claude / "skills" / name, open_dist / ".opencode/skills" / name):
            if not (package / "SKILL.md").is_file():
                raise ValidationError(f"missing generated skill: {package / 'SKILL.md'}")
        if not (codex / "skills" / name / "agents/openai.yaml").is_file():
            raise ValidationError(f"missing Codex metadata for {name}")
        codex_meta = read_text(codex / "skills" / name / "agents/openai.yaml")
        expected = "allow_implicit_invocation: " + ("true" if skill.get("invocation") == "implicit" else "false")
        if expected not in codex_meta:
            raise ValidationError(f"{name}: Codex invocation policy differs from config")
        claude_meta, _ = parse_frontmatter(read_text(claude / "skills" / name / "SKILL.md"), claude / "skills" / name / "SKILL.md")
        if skill.get("invocation", "explicit") == "explicit" and claude_meta.get("disable-model-invocation") != "true":
            raise ValidationError(f"{name}: Claude explicit invocation policy is missing")
        if not (open_dist / ".opencode/commands" / f"{name}.md").is_file():
            raise ValidationError(f"missing OpenCode command for {name}")
    open_package = read_json(open_dist / "package.json")
    if open_package.get("name") != info["npm"]["package"] or open_package.get("version") != ver:
        raise ValidationError("OpenCode package metadata differs from config")
    if open_package.get("exports") != f"./.opencode/plugins/{info['name']}.js":
        raise ValidationError("OpenCode package export is invalid")
    for package in (codex, claude, open_dist):
        validate_package_no_external_paths(package)
    integrity = read_json(output / "integrity.json")
    if integrity.get("version") != ver or set(integrity.get("skills", {})) != {skill["name"] for skill in info["skills"]}:
        raise ValidationError("integrity metadata is incomplete")


def checked_output(raw: str, root: Path = ROOT) -> Path:
    path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError("output must remain inside the repository") from exc
    if path == root.resolve():
        raise ValidationError("output cannot be the repository root")
    protected = (".git", "core", "adapters", "tooling", "dist")
    for relative in protected:
        protected_path = (root / relative).resolve()
        try:
            path.relative_to(protected_path)
        except ValueError:
            continue
        raise ValidationError(f"output cannot be inside protected source/publication path: {relative}")
    return path


def sync_publication(root: Path = ROOT) -> None:
    with tempfile.TemporaryDirectory(prefix="agent-plugin-assembly-") as temp:
        assembled = Path(temp)
        assemble(assembled, root)
        validate_assembly(assembled, root)
        target = root / "dist"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(assembled / "publication/dist", target)


def validate_committed_publication(root: Path = ROOT) -> None:
    """Ensure checked-in distributions match the assembler output."""
    with tempfile.TemporaryDirectory(prefix="agent-plugin-publication-check-") as temp:
        assembled = Path(temp)
        assemble(assembled, root)
        validate_assembly(assembled, root)
        expected = assembled / "publication/dist"
        actual_path = root / "dist"
        if not actual_path.is_dir() or tree_snapshot(actual_path) != tree_snapshot(expected):
            raise ValidationError("committed dist/ is stale; run python tooling/plugin.py sync-publication")


def write_release_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o755 if path.suffix == ".sh" else 0o644) << 16
            archive.writestr(info, path.read_bytes())


def package_release(root: Path = ROOT, output: Path | None = None) -> Path:
    output = output or root / "build/release"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    ver = version(root)
    config = load_config(root)
    with tempfile.TemporaryDirectory(prefix="agent-plugin-release-") as temp:
        assembled = Path(temp)
        assemble(assembled, root)
        validate_assembly(assembled, root)
        source = assembled / "publication/dist/opencode"
        name = plugin_info(config)["name"]
        archive = output / f"{name}-opencode.zip"
        versioned = output / f"{name}-opencode-{ver}.zip"
        write_release_zip(source, archive)
        shutil.copy2(archive, versioned)
        write_text(output / f"{archive.name}.sha256", f"{sha256_bytes(archive.read_bytes())}  {archive.name}")
        for filename, content in render_release_installers(config, default_ref=f"v{ver}").items():
            write_text(output / filename, content)
    return output


def command_assemble(args: argparse.Namespace) -> None:
    output = checked_output(args.output)
    assemble(output)
    validate_assembly(output)
    print(f"Assembled and validated {output.relative_to(ROOT)}")


def command_check(_: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="agent-plugin-check-") as first, tempfile.TemporaryDirectory(prefix="agent-plugin-check-") as second:
        first_path, second_path = Path(first), Path(second)
        assemble(first_path)
        assemble(second_path)
        validate_assembly(first_path)
        validate_assembly(second_path)
        if tree_snapshot(first_path) != tree_snapshot(second_path):
            raise ValidationError("assembly is not deterministic")
    validate_committed_publication()
    print("Source, adapters, and deterministic assembly are valid")


def command_sync(_: argparse.Namespace) -> None:
    sync_publication()
    print("Synchronized generated distributions")


def command_release(args: argparse.Namespace) -> None:
    output = package_release(ROOT, checked_output(args.output) if args.output else None)
    print(f"Packaged release assets under {output.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble and validate a cross-environment agent plugin")
    sub = parser.add_subparsers(dest="command", required=True)
    assemble_parser = sub.add_parser("assemble")
    assemble_parser.add_argument("--output", default="build/assembly")
    assemble_parser.set_defaults(handler=command_assemble)
    check_parser = sub.add_parser("check")
    check_parser.set_defaults(handler=command_check)
    sync_parser = sub.add_parser("sync-publication")
    sync_parser.set_defaults(handler=command_sync)
    release_parser = sub.add_parser("package-release")
    release_parser.add_argument("--output", default="build/release")
    release_parser.set_defaults(handler=command_release)
    args = parser.parse_args()
    try:
        args.handler(args)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
