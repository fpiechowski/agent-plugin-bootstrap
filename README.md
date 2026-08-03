# Agent Plugin Bootstrap

`agent-plugin-bootstrap` is a self-hosting starter for production-ready AI-agent plugins. It keeps one canonical skill core and assembles complete Codex, Claude Code, and OpenCode distributions from the same source tree.

## Bootstrap a plugin

From an installed copy of this repository, invoke the skill explicitly:

- Codex: `$agent-plugin-bootstrap`
- Claude Code: `/agent-plugin-bootstrap:agent-plugin-bootstrap`
- OpenCode: `/agent-plugin-bootstrap`

The skill previews normalized metadata with a dry run, asks for confirmation, and then runs the collision-safe generator. The same operation is available without an agent:

```text
python scripts/init_plugin.py --target <path> --config <metadata.json>
python scripts/init_plugin.py --target <path> --name my-plugin --description "..." --repository https://github.com/acme/my-plugin --author-name "Acme" --npm-scope @acme --npm-package @acme/my-plugin --skill-name my-plugin --skill-description "..."
```

Flags override values from JSON. Existing files are never overwritten; use a new or empty target directory.

## Repository layout

- `core/skills/` — canonical skills and references shared by every host.
- `core/shared/` — optional shared assets for multiple skills.
- `adapters/` — host-specific manifests and extension points.
- `tooling/plugin.py` — deterministic `assemble`, `check`, `sync-publication`, and `package-release` commands.
- `dist/` — committed, self-contained host distributions.

## Development and release

```text
python tooling/plugin.py check
python tooling/plugin.py sync-publication
python tooling/plugin.py package-release
```

`VERSION` is the only version source. A `v<SemVer>` tag runs the release workflow, publishes GitHub Release ZIP assets and installers, and publishes the OpenCode npm package with provenance.

The generated one-line installers are available from the repository's `master` branch for latest development and from `releases/latest/download/` for the newest stable release. Pinned release installers set `PLUGIN_RELEASE_TAG=v<SemVer>` before execution.

For example, install the latest stable OpenCode ZIP with:

```powershell
irm https://github.com/fpiechowski/agent-plugin-bootstrap/releases/latest/download/install-opencode.ps1 | iex
```

## Licensing

MIT. See [LICENSE](LICENSE).
