# Initialization contract

The generator accepts a JSON object with `schemaVersion: 1` and a `plugin` object. Required plugin fields are `name`, `displayName`, `description`, `repository`, `author.name`, `license`, `category`, `npm.scope`, `npm.package`, and one `skills` entry. Each skill requires `name`, `description`, and `invocation` (`explicit` or `implicit`).

The generated project keeps canonical skills under `core/skills/<name>/`. A skill directory contains `SKILL.md` and may contain `references/`, `scripts/`, and `assets/`. Host-only files belong below `adapters/codex/components/`, `adapters/claude-code/components/`, or `adapters/opencode/components/`.

The generator does not overwrite existing files. It stages the complete result, validates it, then copies only paths that do not already exist. `--dry-run` never writes to the target.

Every generated host package is self-contained. No published file may refer to `../` or to a source-only directory outside its package root.
