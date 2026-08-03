# Agent instructions

- Treat `core/` and `adapters/` as canonical sources; do not hand-edit `dist/`.
- Run `python tooling/plugin.py check` after source changes.
- Run `python tooling/plugin.py sync-publication` before committing generated artifacts.
- Keep every published distribution self-contained and free of paths outside its own directory.
- Release only from a `v<SemVer>` tag matching `VERSION`.
- Keep the bootstrap skill explicitly invoked on all hosts.
