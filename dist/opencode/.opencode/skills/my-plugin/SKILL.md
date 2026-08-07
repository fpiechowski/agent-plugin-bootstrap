---
name: my-plugin
description: "A minimal example skill for a cross-host agent plugin."
metadata:
  opencode/autoinvoke: "false"
---

# Purpose

Use this skill as the starting point for the plugin workflow in the current project.

# Workflow

1. Inspect the user's request and the repository state.
2. State the intended changes and the validation you will run.
3. Make the smallest complete change that satisfies the request.
4. Run the relevant checks and report any remaining limitations.

# Boundaries

- Invoke this skill explicitly unless the plugin owner changes the host policy.
- Keep generated artifacts self-contained and preserve unrelated user files.
- Ask before destructive or externally visible operations.
