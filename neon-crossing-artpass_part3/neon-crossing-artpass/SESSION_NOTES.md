# Notes for cloud sessions (Claude main, 2026-10-06) — read after CLAUDE.md

State: 8 districts exist (alley, crossing, shrine done and passed; mall, station, underground, homes, park in test).
This commit = Claude main's current shared files: builder (`art_pass/districts/alley/alley_builder.gd` + `merge_boxes.gd`)
with every builder request from the mall / station / underground / homes / park sessions merged, plus tools.

Shared builder features you can use from inventory data (no code needed):
- `structures` with `dump_index` + `role` (materials by role), `props` (piece/pos/rot), `panels` (thin tiled boxes),
  `district_lights` (baked lamps at any height), `ground_patches` (flat skins <= 2 cm: lawn / paving),
  per building: `roof_is_route`, `plain_faces`, `cornice_depth`; scene exports: SKIP_ROLES, SKIP_IDS, TRAD, DRESS
  (STREET_DRESS.json: MultiMesh props + old boxes they replace), SKYLINE_CENTER / SKYLINE_RADII, `_district_extras()` hook.
- Convex/concave collider visuals are merged automatically (flat normals). Window/sign quads are merged per cell.
- Tools: `tools/check_openings.gd` (doorway self-check, incl. MultiMesh), `tools/district_check.sh <district>`
  (build + check + 6 renders), `tools/inventory/street_dress.py`.

Repo layout is messy (three part folders). First task of the next session: flatten it so the project root holds
project.godot + art_pass/ + render_cams.* + tools/ (git mv, one commit), keeping every file once (newest wins).
