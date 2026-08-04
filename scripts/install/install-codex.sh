#!/usr/bin/env sh
set -eu
name="agent-plugin-bootstrap"
source="fpiechowski/agent-plugin-bootstrap"
default_ref=""
plugin_id="agent-plugin-bootstrap@agent-plugin-bootstrap"
if ! command -v codex >/dev/null 2>&1; then echo "Codex CLI was not found on PATH." >&2; exit 1; fi
if [ -n "${PLUGIN_RELEASE_TAG:-}" ]; then ref="${PLUGIN_RELEASE_TAG}"; elif [ -n "$default_ref" ]; then ref="$default_ref"; else ref="master"; fi
marketplaces="$(codex plugin marketplace list --json 2>/dev/null || true)"
if printf '%s
' "$marketplaces" | grep -Eq '"name"[[:space:]]*:[[:space:]]*"agent-plugin-bootstrap"'; then
  codex plugin remove "$plugin_id" >/dev/null 2>&1 || true
  codex plugin marketplace remove "$name" >/dev/null 2>&1 || true
fi
codex plugin marketplace add "$source" --ref "$ref"
codex plugin add "$plugin_id"
echo "agent-plugin-bootstrap is installed from $ref. Start a new Codex conversation."
