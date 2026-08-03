# Host adapters

The assembler owns the generated manifest shape. Add host-only payloads below the matching `components/` directory:

- Codex: `.mcp.json`, `.app.json`, and `assets/`.
- Claude Code: `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, and `.lsp.json`.
- OpenCode: `mcp.json`, runtime/plugin helpers, and any `tools/` or `agents/` payloads consumed by the generated plugin.

Optional manifest fields are emitted only when their corresponding files exist.
