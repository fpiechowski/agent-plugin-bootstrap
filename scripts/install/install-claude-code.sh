#!/usr/bin/env sh
set -eu
name="agent-plugin-bootstrap"
source="fpiechowski/agent-plugin-bootstrap"
default_ref=""
plugin_id="agent-plugin-bootstrap@agent-plugin-bootstrap"
if ! command -v claude >/dev/null 2>&1; then echo "Claude Code CLI was not found on PATH." >&2; exit 1; fi
if [ -n "${PLUGIN_RELEASE_TAG:-}" ]; then ref="${PLUGIN_RELEASE_TAG}"; elif [ -n "$default_ref" ]; then ref="$default_ref"; else ref="master"; fi
marketplaces="$(claude plugin marketplace list --json 2>/dev/null || true)"
if printf '%s
' "$marketplaces" | grep -Eq '"name"[[:space:]]*:[[:space:]]*"agent-plugin-bootstrap"'; then
  claude plugin uninstall --scope user "$plugin_id" >/dev/null 2>&1 || true
  claude plugin marketplace remove "$name" >/dev/null 2>&1 || true
fi
claude plugin marketplace add --scope user "$source@$ref"
claude plugin install --scope user "$plugin_id"
echo "agent-plugin-bootstrap is installed from $ref. Restart Claude Code or run /reload-plugins."
