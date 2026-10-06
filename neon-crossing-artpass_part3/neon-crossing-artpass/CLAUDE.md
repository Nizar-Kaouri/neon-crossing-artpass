# Neon Crossing — art pass (cloud sessions)

Godot 4.7 project. We dress the OLD lab map of a multiplayer parkour shooter in the approved art style, one district
at a time. The layout is FROZEN: same buildings, positions, sizes and routes as the old map.

## Hard rules
1. **Visual layer only.** Never add, move, remove or resize collision. The old map's collision is rebuilt from
   `art_pass/export/layout_dump.json` by the builder (`standalone = true`) and must stay identical.
2. **Never block a doorway or a walkable surface.** Nothing visual below 2.05 m inside any opening; nothing inside a
   stair/landing volume up to +2 m; cladding stays 5 cm outside collision faces.
3. **Do not edit shared files**: `art_pass/districts/alley/alley_builder.gd`, `merge_boxes.gd`, `art_pass/slice/*`,
   `art_pass/kit/*`, `art_pass/shaders/*`, `art_pass/export/*`. If your district needs a builder feature, write it in
   `art_pass/districts/<district>/BUILDER_REQUESTS.md` (what, why, exact proposed code). Claude (main) merges builder changes.
4. **Only your own folder**: `art_pass/districts/<district>/`. Work on branch `district/<district>`, open a PR when done.
5. **Budget** (`art_pass/BUDGET.md`): Low preset ≤ 3.5 ms and ≤ 800 draw calls per view for the map. Cloud renders use a
   different renderer, so only use their draw-call count as a rough guide (cloud ≈ 1.5–2× the real Low count).
6. **Free assets only.** Reuse the kit (`art_pass/kit`), props (`art_pass/props`), textures (`art_pass/textures/tiling`).
7. Never mention or add sound.

## Setup (once per session)
`bash tools/setup_cloud.sh` — installs Godot 4.7.1, xvfb, numpy/scipy/pillow and imports the project.

## How a district is made (copy the crossing / shrine pattern)
1. Region: `art_pass/districts/REGIONS.json` (rects [x0, z0, x1, z1], world metres, north = −z).
2. Inventory from the dump: `cd art_pass && python tools/inventory/inventory.py <name> x0 z0 x1 z1 <PREFIX> districts/<name>/<NAME>_INVENTORY.json`
   (buildings: footprint, roof, ground-floor openings). For non-building areas write a `structures` list with roles like
   `SHRINE_INVENTORY.json` (see `tools/inventory/shrine_props.py`). Check the result against `districts/regions_map.png`
  ; fix kinds/names by hand where useful.
3. Convex hull visuals: `python tools/convex_hulls.py x0 z0 x1 z1 districts/<name>/old_convex_hulls.json`
4. Scene: copy `districts/crossing/crossing.tscn`, set INV, HULLS, REGION (bounding Rect2), TRAD kinds, SKIP_IDS, CABLES.
5. `cameras.json`: 6 cameras (2–3 street level 1.7 m, 1 roof, 1 high overview); keys 1/2/3 in the viewer = cameras 1/5/6.
6. Test renders:
   `xvfb-run -a -s "-screen 0 1600x900x24" godot --rendering-driver opengl3 --path . res://render_cams.tscn -- --scene=res://art_pass/districts/<d>/<d>.tscn --cams=res://art_pass/districts/<d>/cameras.json --out=renders/<d>_v0`
   Look at every image. The builder prints `DISTRICT <name>: merged boxes into N meshes ...` — no SCRIPT ERROR allowed.
7. Self-check before the PR: no visual mesh in any opening / stair volume (write a small script like shrine_props.py does),
   and a `districts/<name>/REPORT.md`: what you built, the 6 renders, draw calls, known problems, builder requests.

## What happens after your PR
Nizar bakes the scene on his PC; ChatGPT runs the real tests there (player route walks vs the old map, doorway safety,
FPS). A district passes with 0 route regressions, 0 doorway intrusions and Low ≤ 3.5 ms / ≤ 800 draws.

## Style
Target look: `art_pass/STYLE.md` (dusk, warm lanterns, lavender sky, cream plaster / timber / concrete, neon accents).
