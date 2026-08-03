---
name: agent-plugin-bootstrap
description: "Create a new production-ready AI-agent plugin with one shared core and Codex, Claude Code, and OpenCode distributions. Invoke explicitly when the user wants to bootstrap, scaffold, or standardize an agent plugin repository."
disable-model-invocation: true
---

Use this skill only when the user explicitly asks to bootstrap, scaffold, or standardize an agent plugin repository.

The bundled generator is the source of truth for repository creation. First understand the requested plugin and collect these values:

- plugin name and user-facing display name;
- one-sentence and long descriptions;
- repository URL and author metadata;
- license, category, brand color, and npm scope/package name;
- target directory;
- initial skill name, description, and explicit invocation policy;
- any host-specific components that should be included at bootstrap time.

Before writing files, run the generator in dry-run mode and show the normalized metadata and planned tree. Ask the user to confirm that preview. Only after confirmation run the same command without `--dry-run`.

Use the bundled script at `scripts/init_plugin.py` relative to this plugin's package root. The direct, non-interactive interface is:

```text
python scripts/init_plugin.py --target <path> --config <json-file>
```

Flags may be used instead of the JSON file and override values loaded from it. Never use a force flag: the generator refuses file collisions and writes through a temporary staging directory. If the target is not suitable, explain the exact collision and ask the user for another target.

After generation, tell the user to run:

```text
python tooling/plugin.py check
```

The generated repository is ready for `sync-publication`, a tagged release, and installation through the Codex or Claude Code marketplace or the OpenCode ZIP/npm channel.

Read `references/initialization-contract.md` before executing the generator.
