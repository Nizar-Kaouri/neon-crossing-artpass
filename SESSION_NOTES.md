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

Repo layout: flattened (2026-10-06): project.godot + art_pass/ + render_cams.* + tools/ at the root.

Ground pass (2026-10-06, `art_pass/districts/REPORT_GROUND.md`): `districts/<d>/GROUND_DETAIL.json` for all 8
districts (asphalt, kerbs, scramble paint, manholes, drain covers, patches, puddles; flat, +0.7..1.9 cm, no collision),
made by `art_pass/tools/inventory/ground_detail.py`, checked by `ground_check.py`. Drawn only once builder request G1
(`districts/GROUND_BUILDER_REQUEST.md` / `.patch`, `_ground_detail()`) is merged.
