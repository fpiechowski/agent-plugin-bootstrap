#!/usr/bin/env sh
set -eu
scope="global"; project_path="$(pwd)"
if [ "$#" -ge 1 ]; then scope="$1"; fi
if [ "$#" -ge 2 ]; then project_path="$2"; fi
source_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
case "$scope" in
  global) config_root="$HOME/.config/opencode" ;;
  project) config_root="$(CDPATH= cd -- "$project_path" && pwd)/.opencode" ;;
  *) echo "usage: sh ./install.sh [global|project] [project-path]" >&2; exit 2 ;;
esac
mkdir -p "$config_root"
for folder in skills commands plugins; do
  if [ -d "$source_root/.opencode/$folder" ]; then mkdir -p "$config_root/$folder"; cp -R "$source_root/.opencode/$folder"/. "$config_root/$folder"/; fi
done
echo "Installed my-plugin 0.1.0 for OpenCode at $config_root"
