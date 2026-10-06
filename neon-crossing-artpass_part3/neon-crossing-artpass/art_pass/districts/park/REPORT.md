# PARK district: report (Claude, cloud, 2026-10-06)

Region (`REGIONS.json`): `[-72, 125, 2, 180]` + `[2, 110, 100, 180]`. Scene REGION = `Rect2(-72, 110, 172, 70)`.
Branch `district/homes-park`. Only files in `art_pass/districts/park/` (and `homes/`). No shared file is edited.

## What is in the district (from the dump)
A **flat** park inside the boundary walls (z 164, x 18). The ground slab top is y 0, over x -72..18, z 100..164.
The furniture is filed under two names in the dump. I checked it against `regions_map.png`:
- `FullMapNativeRebuild` / `Step4Layout`: 4 benches (3.2 × 0.8 m seat at 0.5 m) and 2 garden corners (2 m stone L-walls
  + a 0.9 m planter);
- `@Node3D@9344/Collision/MallStaticCollision`: park pieces stored under the mall node. They are 8 tree trunks
  (0.5 × 0.5 × 2.8 m), 4 benches with backs, 4 raised planting beds on the lawns (6 × 2.5 × 1.17 m) and 2 shelters
  (counter, posts, 3.8 × 3 m roof at 2.6–2.75 m).
- **Routes** (dump `routes`): N-S paths x -70 / -35 / 0 (3.8 m), cross paths z 146 (3.2 m) and z 160 (3.8 m).
- The lawns (x -50.9..-37 and -33.1..-18.9, z 137.7..156) have no collision: they were paint on the slab.

`inventory.py` finds no buildings here, so the inventory is a `structures` role list (shrine pattern).

## What I built (park painting style, the old flat layout unchanged)
- **Materials by role** (no new material): timber bench seats and backs, stone garden walls / planters / bed bodies /
  shelter counters, moss + grass tops on the planting beds (planted look, no props on top), tiled shelter roofs, timber
  posts and trunks, dark metal bench legs.
- **Trees**: 3 crowns (pine, 2 sakura accents) on each of the 8 old trunk colliders, starting at 2.4 m. The trunks at
  x -69 / -1 stand on the outer N-S paths in the old map; they stay where they are.
- **Lamps**: 7 lantern posts (one beside each bench where a spot clears every collider by 0.4 m and every route by 0.6 m,
  plus the 4 ends of the central path) with baked lights, and 4 bollard lamps at the lawn corners.
- **Planting**: 20 shrubs beside the planters and planting beds, with the same clearance rule.
- **Ground**: lawns + the 5 paved paths as 1 cm `ground_patches` (R2), and a lawn strip + treeline (22 trees) beyond the
  boundary walls as backdrop.
- `old_convex_hulls.json`: `tools/convex_hulls.py -72 110 100 180`, filtered to empty by `make_inventory.py`. All 758
  hulls in that box are the mall's convex shell, which the mall district dresses. Drawn here they cost 2 300 draw calls.
- `park.tscn` (crossing pattern), `cameras.json` (4 street cameras at 1.7 m, 1 from the shelter / wall height at 3.8 m,
  1 high overview), `make_inventory.py`, and the self-check tools `dump_tris.gd` + `self_check.py`.

## Builder requests
Only R2 (flat ground patches). It is specified in `districts/homes/BUILDER_REQUESTS.md` + `homes/builder_requests.patch`;
see `BUILDER_REQUESTS.md` here.

## Renders (`renders/`, 1600×900, no bake)
`park_v0_N.jpg` = the shared builder as it is today (no lawns). `park_req_N.jpg` = with R2 applied.

| cam | view | draw calls (current) | draw calls (with R2) |
|---|---|---|---|
| 1 | Central path, looking south between the lawns | 200 | 215 |
| 2 | Middle cross path, looking east | 280 | 295 |
| 3 | South cross path, looking west | 261 | 270 |
| 4 | West bench, looking south-east | 287 | 302 |
| 5 | West shelter height (3.8 m), looking east | 285 | 300 |
| 6 | High overview from the south-east | 259 | 269 |

Max 302 cloud draw calls, well under the 800 Low limit. Merged meshes: 26 (30 with R2).
`DISTRICT Park: merged boxes into 26 meshes, quads into 6, 92 small props cast no shadow`, no SCRIPT ERROR.

## Self-check (`SELF_CHECK_*.json`)
All ~22 k built triangles are tested against 5 route corridors (+2.05 m), 18 walkable tops (bench seats, planters, beds,
counters, shelter roofs; +2 m) and 0 openings.

| | route corridors | walkable tops | openings | result |
|---|---|---|---|---|
| current shared builder | 0 | 0 | 0 | **PASS** |
| with R2 | 0 | 0 | 0 | **PASS** |

Open-ground dressing, listed for review: 7 lantern posts, 4 bollards and 20 shrubs, all ≥ 0.6 m from every route
corridor and ≥ 0.4 m from every collider. Tree crowns start at 2.4 m.

## Known problems
- **No lawns or paved paths** until R2 is merged (plain ground slab). The backdrop treeline then stands on nothing,
  outside the map, with no gameplay effect.
- **Square trunks**: the old trunk colliders are drawn as 0.5 m square timber boxes under the crowns. A round kit
  trunk would need a builder option to hide one old collider's visual (not requested; the collision must stay).
- **Mall shell missing in this scene**: the park scene doesn't draw the mall's convex shell (see above), so park cameras
  looking north show only its box parts. The full map is unaffected.
- One bench (west, z 153, wedged between the shelter, the planter and the garden wall) has no lantern post, because no
  candidate spot cleared everything.
- The lamp lights are baked (hidden at runtime), so cloud renders show no lamp glow until Nizar's bake.
