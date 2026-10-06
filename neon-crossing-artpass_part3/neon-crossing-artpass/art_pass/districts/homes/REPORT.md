# HOMES district: report (Claude, cloud, 2026-10-06)

Region (`REGIONS.json`): `[31, 2, 100, 110]` + `[2, 30, 31, 110]`. Scene REGION = `Rect2(2, 2, 98, 108)` (bounding box).
Branch `district/homes-park`. Only files in `art_pass/districts/homes/` (and `park/`). No shared file is edited.

## What is in the district (from the dump)
10 houses that **cannot be entered**. The dump has no doorway gap in any of them; the inventory has 0 openings.
- **A1, A2, A3**: apartment blocks, 12.9–17.6 m, balcony terraces on each floor, and an outdoor *service flight*
  (zig-zag ramps + fold landings) on the west side that climbs to the roof (A1: 5 flights).
- **V1–V7**: villas, 6.8–9.6 m, each with a garden wing (3.7–5.2 m) whose roof carries a sun terrace, a fold landing,
  a 2-flight service stair to the roof and a roof threshold.
- 10 garden plots bounded by 0.6 m kerbs; the residential green (x 42–58, z 54–68: tree trunk, 2 lamp posts, 2 raised beds);
  the courtyard screen wall at z 52.
- **Routes** (dump `routes`): Northern residential walk, Southern garden promenade, Apartment lane, Estate lane (4–5.5 m),
  and the 25 service-flight segments. Walkable tops: 105 (roofs, balconies, sun terraces, landings, thresholds, beds).

`tools/inventory/inventory.py` was run on both rects first. It finds the same 24 slab clusters (body / wing pairs), all
with `wall_cover` 1.0 and no openings, but it cannot name them. `make_inventory.py` builds the inventory from the named
`FullMapNativeRebuild` shapes (A1Body, V3GardenWingRoof, …) instead, so every entry keeps its old name.

## What I built
- `HOMES_INVENTORY.json` (`make_inventory.py`):
  - 18 building entries (10 bodies + 8 garden wings), kinds `apartment_block` / `house` / `house_wing`. These are plain
    (not TRAD): no eaves, noren or porch posts over the 3.3–3.6 m balconies, and no ivy. Every entry has
    `roof_is_route: true` and `cornice_depth` 0.12 (0.11 next to a flight).
  - `structures`: stone kerbs and screen, timber bed edging, tree trunk.
  - Props: 3 crowns on the old trunk, lantern posts **on** the two old 2.3 m post colliders, 15 shrubs in plot corners
    (any corner on a route corridor is skipped), and a treeline outside the boundary walls (x 92 / z 100).
  - 2 baked lamp lights, and 13 `ground_patches` (lawn plots + residential green + backdrop strip).
- `old_convex_hulls.json`: `tools/convex_hulls.py 2 2 100 110` (30 hulls, the service-flight ramps).
- `homes.tscn`: the crossing pattern (same environment, sun, LightmapGI, viewer camera).
- `cameras.json`: 4 street cameras at 1.7 m, 1 roof camera (V2 roof, eye 10 m) and 1 high overview. Viewer keys 1/2/3 =
  cameras 1/5/6.
- Self-check tools: `dump_tris.gd` writes every built triangle, `self_check.py` tests them (method in its header).

## Builder requests: `BUILDER_REQUESTS.md` + `builder_requests.patch`
R1 no roof antenna on route roofs · R2 flat ground patches (lawns) · R3 per-building cornice depth · R4 plain faces
(no windows next to a flight). All are data-driven; other districts build unchanged. I tested the patch locally without
committing it.

## Renders (`renders/`, 1600×900, no bake, cloud GL Compatibility)
`homes_v0_N.jpg` = the shared builder as it is today. `homes_req_N.jpg` = with the four requests applied.

| cam | view | draw calls (current) | draw calls (with requests) |
|---|---|---|---|
| 1 | Northern residential walk, looking east | 271 | 274 |
| 2 | Apartment lane, looking north at the A3 / V1 flights | 187 | 196 |
| 3 | Estate lane, looking north | 290 | 291 |
| 4 | Southern promenade, looking west | 298 | 294 |
| 5 | V2 roof, looking north-west | 249 | 247 |
| 6 | High overview from the south-east | 240 | 239 |

Max 298 cloud draw calls (cloud ≈ 1.5–2× real Low), well under the 800 Low limit. Merged meshes: 27 (33 with R2).
No new materials. `DISTRICT Homes: merged boxes into 27 meshes, quads into 10, 38 small props cast no shadow`, no SCRIPT ERROR.

## Self-check (`SELF_CHECK_*.json`)
All 34–35 k built triangles, sampled every 8 cm (20 cm on faces over 3 m). They are tested against 40 route corridors
(including every service flight, from its sloped surface to +2.05 m), 105 walkable tops (+2 m) and 0 openings.

| | route corridors | stair / flight volumes | walkable tops | openings | result |
|---|---|---|---|---|---|
| **with requests R1–R4** | 0 | 0 | 0 | 0 | **PASS** |
| current shared builder | 0 | 2 meshes | 7 | 0 | FAIL |

With the current builder the failures are exactly what the requests fix:
- 7 `P_roof_antenna` on the A1, A2, A3, V2, V3, V6 and V7 roofs (R1);
- cornices (0.28 m) 2–6 cm into the A2 / V2 / V3 / V7 flight corridors near the roof, and window frames 9 cm into the
  V1 flight (R3, R4).

Open-ground dressing, listed for review: 15 shrubs in garden plots. None is on a route, flight, roof or terrace.

## Known problems
- **Blank ground floors.** The houses cannot be entered, so the builder clads the ground floor solid and puts windows
  only on the upper floors. Ground-floor windows or a porch light would need another builder option (not requested).
- **Current builder = antennas on route roofs** until R1 is merged, plus the R3 / R4 cornice and window intrusions.
- **No lawns** until R2 is merged: the plots show the plain ground slab, and the backdrop trees beyond x 92 / z 100
  stand on nothing (outside the map; no gameplay effect).
- **Cladding vs. V1–V7 flights:** the standard cladding (outer face 11 cm off the wall) overlaps the outer 1 cm of the
  flights that run 10 cm from the wall. This is accepted in the self-check as wall skin (≤ 12 cm in flight volumes).
- The scene's bounding REGION also draws the undressed old visuals of the crossing corner (x 2–31, z 2–30). This matches
  the other districts.
- The lamp lights are baked (hidden at runtime), so cloud renders show no lamp glow until Nizar's bake.
