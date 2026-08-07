# Agent instructions

- Treat `core/` and `adapters/` as canonical sources; do not hand-edit `dist/`.
- Keep the example skill explicitly invoked on all hosts unless the plugin owner chooses otherwise.
- Run `python tooling/plugin.py sync-publication` after source changes, then run `python tooling/plugin.py check`.
- Keep every published distribution self-contained and free of paths outside its own directory.
- Release only from a `v<SemVer>` tag matching `VERSION`.
