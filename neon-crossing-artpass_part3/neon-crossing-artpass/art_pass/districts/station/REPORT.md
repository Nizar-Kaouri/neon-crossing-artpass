# Station — district report (Claude, cloud, 2026-10-06)

Region `station` = rect [-120, -90, -72, 180] (REGIONS.json). Old map structures are all at z -77 .. 73.

## What is there (old layout, unchanged) and its roles (`STATION_INVENTORY.json`)
| Role | Dump indices | What |
|---|---|---|
| `viaduct_deck` | 876 | deck x -91..-73, top y 11, z -73..73 |
| `track_rail` | 896–899 | rails at x -88/-84 (west track, no train) and -81/-77 (**east track: the lethal express**, x -79) |
| `viaduct_column` | 882–895 | 14 columns, 1.4 x 2 m, every ~24 m at x -90 / -76 |
| `platform` | 877, 878 | 2 m side platform x -93..-91 at y 11 |
| `shelter_wall` / `shelter_roof` / `canopy_post` | 1880, 1882 / 1879, 1881 / 10319–10326 | two platform shelters, canopy posts |
| `platform_bench` | 4016–4021 | 2 benches on the platform |
| `track_canopy_roof` | 881 | walkable roof over the tracks (y 14.5), stair 913 up from the deck |
| `raised_platform` / `_roof` | 879 / 880 | mid platform y 5.5 west of the viaduct, roof at y 8.7..9.3 |
| `stair_flight` | 907, 900, 910, 913, 1815, 1818 | street -> raised platform (2), raised -> side platform (910), deck -> canopy roof (913), street -> underground (2). Axis + ends from the hull (`dresslib.stair_axis`), y ends match the landings exactly |
| `stair_flight_ramp` | 904 | raised -> side platform, drawn as ramp (see R7) |
| `stair_landing` | 13 boxes | top/bottom landings of every flight |
| `info_island_wall` / `_lintel` / `_roof` | 1847–1878 | **2 information islands** under the viaduct (x -92..-73, z -30..-6 and 12..36), 2 rooms each, 3.2 m doors (lintel 2.7 m) on all 4 sides |
| `island_bench` / `island_table` | 3968–4015 | benches and tables inside the islands |
| `ground` / `foundation` | 368 | plain slabs y -1..0 / -5..-1 |
| `underground (see districts/underground)` | 16 | tunnel colliders whose centre is in this rect |
| `map_boundary` | 1844–1846 | > 30 m walls, never drawn |

The two islands are also listed as `buildings` (S01 "konbini" = ticket kiosk, S02 "info_centre"), footprint = outer wall
faces, the 4 doors measured from the wall gaps, so the shared builder clads them (5 cm outside the walls, holes at the
doors), adds light-box signs, flush shop windows, pots beside the doors and door lights.
The auto tool `inventory.py` got the footprint wrong (roof slab instead of walls) and missed the east doors, so this
inventory is written by `station_props.py`.

## What I added (visual only, 93 props, `station_props.py`)
- 20 wall lamps on the 10 columns outside the islands (y 3.4, both faces) + 10 baked lamp lights;
- 12 paper lanterns under the raised-platform roof (2.57 m clear) + 2 lights at y 6.9;
- 5 paper lanterns under the canopy roof over the **west** track only (2.27 m clear over the deck; nothing hangs
  over x > -82.5, where the express runs, top 13.83);
- 2 lit station-name light boxes on the shelter walls (bottom 2.1 m over the platform), 2 hanging name boards under
  the canopy roof;
- express warning line: dashed yellow rib tiles on the deck just west of the express track (42 x 1 m, every 3 m,
  stair 913 left clear);
- 2 "to underground / mall" light boxes on the columns at the stair wells (over the pit, never over a floor);
- tactile dot rows at the street foot of the two street stairs.
Platform-level lights (7) wait for builder request R2.

## Test renders (current shared builder) — `shots/station_v0_<n>.jpg`
| # | Camera | Cloud draw calls |
|---|---|---|
| 1 | street under the viaduct, north island (doors, windows, pots, column lamps) | 209 |
| 2 | side platform looking south along the tracks (shelter sign, lanterns, warning line) | 296 |
| 3 | raised platform under the lantern roof | 235 |
| 4 | street, north stair well and column lamps | 295 |
| 5 | track canopy roof edge over stair 913 | 215 |
| 6 | high overview from the north-west | 268 |

Max 296 cloud draw calls (≈ 150–200 on the real Low preset by the 1.5–2x rule), well under 800.
`DISTRICT Station: merged boxes into 31 meshes, quads into 8, 129 small props cast no shadow`, no SCRIPT ERROR.
`shots/station_preview_<n>.jpg`: same cameras with the requested builder patch applied on a scratch copy (only R2 lights
change here; lamps kept live to stand in for the bake).

## Self-check (`selfcheck.py station`, result in `selfcheck_result.json`)
Godot builds the scene and samples every visual triangle near a safety volume; Python tests the points.
- 8 doorway volumes (island doors, sill + 2 cm .. + 2.05 m, wall thickness + 30 cm each side): **0 intrusions**
- 7 stair flights (ramp + 10 cm .. + 2 m) and 13 landings (+ 2 cm .. + 2 m): **0 intrusions** (after 904 -> ramp)
- 93 props: 43 at >= 2.05 m above the floor below them, 50 flush on the floor (tactile), **0 floor props**
- Found and reported, not mine: the shared skyline card passes through landing 909 (R5).
Same result with the builder patch (`selfcheck_result_preview.json`).

## Known problems
- **Skyline card through the station** (shared `_skyline()`, 125 m around the origin): R5.
- **The express has no visual**: it is a moving game body; R6. The danger is only the yellow line for now.
- The station surfaces are the builder's default materials (concrete / warm paving); station-specific role
  materials (platform edge trim, track bed) would help readability but I kept the request list short.
- Elevated stairs 910/913 are drawn as solid stepped blocks down to `y_low - 0.3` with cheek walls (shrine style).
- The two big stair-well pits at street level have no visual edge marking (a railing would look like cover that
  is not there; left as in the old map).

## Builder requests
`BUILDER_REQUESTS.md`: R2 district lights, R5 skyline radius, R6 express visual (game side), R7 cheek walls on
landings, R8 warning line as one panel. R1–R3 code: `../underground/BUILDER_REQUESTS.md`.

## Regenerate
```
cd art_pass && python districts/station/station_props.py          # inventory + old_convex_hulls.json
cd .. && xvfb-run -a -s "-screen 0 1600x900x24" godot --rendering-driver opengl3 --path . res://render_cams.tscn -- \
  --scene=res://art_pass/districts/station/station.tscn --cams=res://art_pass/districts/station/cameras.json --out=renders/station_v0
python art_pass/districts/station/selfcheck.py station
```
