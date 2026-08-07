# Agent Plugin Template

Use this repository as a GitHub repository template for a plugin that works across Codex, Claude Code, and OpenCode.

## Start a plugin

1. Select **Use this template** on GitHub.
2. Rename the example values in `plugin.config.json`, including the plugin name, author, repository, and npm package.
3. Rename `core/skills/my-plugin/` and update the skill frontmatter and prompt.
4. Add host-specific components under the matching `adapters/*/components/` directory.
5. Regenerate the committed host distributions:

```text
python tooling/plugin.py sync-publication
python tooling/plugin.py check
```

The canonical sources live in `core/` and `adapters/`. The generated, self-contained packages are in `dist/codex`, `dist/claude-code`, and `dist/opencode`.

`VERSION` controls release versioning. The release workflow can package the OpenCode ZIP and npm distribution after the example metadata has been replaced.

See [LICENSE](LICENSE) for licensing terms.
