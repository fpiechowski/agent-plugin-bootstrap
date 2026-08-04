#!/usr/bin/env sh
set -eu
scope="global"
project_path="$(pwd)"
if [ "$#" -ge 1 ]; then scope="$1"; fi
if [ "$#" -ge 2 ]; then project_path="$2"; fi
default_ref=""
if [ -n "${PLUGIN_RELEASE_TAG:-}" ]; then ref="${PLUGIN_RELEASE_TAG}"; elif [ -n "$default_ref" ]; then ref="$default_ref"; else ref=""; fi
tmpdir="/tmp"
if [ -n "${TMPDIR:-}" ]; then tmpdir="$TMPDIR"; fi
tmp="$tmpdir/agent-plugin-bootstrap-$$"
mkdir -p "$tmp"
trap 'rm -rf "$tmp"' EXIT INT TERM
archive="$tmp/agent-plugin-bootstrap-opencode.zip"
if [ -n "$ref" ]; then url="https://github.com/fpiechowski/agent-plugin-bootstrap/releases/download/$ref/agent-plugin-bootstrap-opencode.zip"; else url="https://github.com/fpiechowski/agent-plugin-bootstrap/releases/latest/download/agent-plugin-bootstrap-opencode.zip"; fi
if command -v curl >/dev/null 2>&1; then curl -fsSL "$url" -o "$archive"; else wget -q "$url" -O "$archive"; fi
command -v unzip >/dev/null 2>&1 || { echo "unzip is required." >&2; exit 1; }
unzip -q "$archive" -d "$tmp/dist"
sh "$tmp/dist/install.sh" "$scope" "$project_path"
