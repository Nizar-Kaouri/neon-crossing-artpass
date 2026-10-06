#!/usr/bin/env bash
# One-time setup in a cloud session: Godot 4.7.1 (Linux), xvfb for renders, python deps for the inventory tools.
set -e
if ! command -v godot >/dev/null; then
  cd /tmp
  curl -sSL -o godot.zip https://github.com/godotengine/godot/releases/download/4.7.1-stable/Godot_v4.7.1-stable_linux.x86_64.zip
  unzip -q -o godot.zip && sudo mv Godot_v4.7.1-stable_linux.x86_64 /usr/local/bin/godot 2>/dev/null || mv Godot_v4.7.1-stable_linux.x86_64 /usr/local/bin/godot
fi
command -v xvfb-run >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq xvfb libgl1 libglu1-mesa) || echo "WARN: no xvfb - builds still work headless, renders won't"
pip install -q numpy scipy pillow 2>/dev/null || pip install -q --break-system-packages numpy scipy pillow
cd "$(dirname "$0")/.." && godot --headless --import --path . >/dev/null 2>&1 || true
godot --version
