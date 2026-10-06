#!/usr/bin/env bash
# Review a district in one go (cloud or any Linux with Godot + xvfb): build log, doorway self-check, 6 test renders.
#   bash art_pass/tools/district_check.sh <district>        (run from the project root)
set -u
d="$1"; scn="res://art_pass/districts/$d/$d.tscn"; cams="res://art_pass/districts/$d/cameras.json"
echo "== build"
timeout 300 xvfb-run -a godot --rendering-driver opengl3 --path . "$scn" --quit-after 20 2>&1 | grep -E "DISTRICT|SCRIPT ERROR|Parse Error" || echo "(no DISTRICT line: builder did not run)"
echo "== doorway self-check (added visuals only)"
timeout 600 godot --headless --path . -s res://art_pass/tools/check_openings.gd -- --scene="$scn" 2>&1 | grep -E "CHECK|HIT|first|ERROR"
echo "== renders -> renders/${d}_check_N.png"
timeout 600 xvfb-run -a -s "-screen 0 1600x900x24" godot --rendering-driver opengl3 --path . res://render_cams.tscn -- --scene="$scn" --cams="$cams" --out="renders/${d}_check" 2>&1 | grep -E "SHOT|ERROR"
