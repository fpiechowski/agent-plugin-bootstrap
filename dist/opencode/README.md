# Agent Plugin Bootstrap

Generate a maintainable plugin repository with one canonical skill core, Codex and Claude Code marketplaces, OpenCode ZIP and npm distributions, deterministic assembly, validation, and release automation.

## Development

```text
python tooling/plugin.py check
python tooling/plugin.py assemble
python tooling/plugin.py sync-publication
python tooling/plugin.py package-release
```

## Installation

Codex (PowerShell):

```powershell
irm https://raw.githubusercontent.com/fpiechowski/agent-plugin-bootstrap/master/scripts/install/install-codex.ps1 | iex
```

Claude Code (PowerShell):

```powershell
irm https://raw.githubusercontent.com/fpiechowski/agent-plugin-bootstrap/master/scripts/install/install-claude-code.ps1 | iex
```

OpenCode npm:

```text
opencode plugin @fpiechowski/agent-plugin-bootstrap --global
```

OpenCode Release ZIP:

```powershell
irm https://raw.githubusercontent.com/fpiechowski/agent-plugin-bootstrap/master/scripts/install/install-opencode.ps1 | iex
```

Stable OpenCode release asset:

```powershell
irm https://github.com/fpiechowski/agent-plugin-bootstrap/releases/latest/download/install-opencode.ps1 | iex
```

Pinned release:

```powershell
$env:PLUGIN_RELEASE_TAG = "v0.1.0"; irm https://github.com/fpiechowski/agent-plugin-bootstrap/releases/latest/download/install-opencode.ps1 | iex
```

The release 0.1.0 is reproducible with tag v0.1.0. Review remote scripts before piping them into a shell.
