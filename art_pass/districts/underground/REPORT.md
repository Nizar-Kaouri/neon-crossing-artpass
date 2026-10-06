# Underground — district report (Claude, cloud, 2026-10-06)

The tunnel from the station to the mall's lowest floor. Inventory rect x -95..-62.5, z -70..86, y -5.36..0
(the plain foundation slabs are ignored except where they are the tunnel's floor or ceiling).

## The old layout (unchanged), from the dump
Floor y -5 (deep floor grid y -6..-5), ceiling y -1 (underside of the street slabs), **4 m clear**.
1. **North stair well**: ramp 1818 (x -82.75..-79.25) from the street (z -66, y 0) down to z -48.5, in a stair room
   x -86..-71.5, z -68..-46 that is open to the sky.
2. **Main corridor** x -82..-72 (10 m wide), z -46..61. Walls 1821 / 1897–1899 (0.35 m), elsewhere slab faces.
3. **Two side rooms** east of it (x -71.65..-63, z -35..-25 and 5..15), entered through 3 m gaps in the x -72 wall.
   Their north/south doorways (2.6 x 2.7 m, lintels 1885/1888/1892/1895) open onto solid ground: dead-end alcoves.
4. **South stair room** x -94..-82, z 42..63 with ramp 1815 from the street (z 61, y 0).
5. **South branch** x -80..-74 (thin mall walls 8313/8314 from z 59) to z 84, with two mall benches,
   then the **link** x -74..-65, z 78..84 into the **mall's lowest floor** (y -5) through the gap in the oval wall
   (x -65, z 76..86). The closed area x -73.8..-65, z 61..71 behind wall 8313 is not reachable.

## Inventory (`UNDERGROUND_INVENTORY.json`, made by `underground_props.py`)
| Role | Count | Notes |
|---|---|---|
| `stair_flight` | 2 | 1815, 1818, with axis (y ends -5.0 / 0.0 match the landings) |
| `stair_landing` | 4 | 1816/1819 at the street, 1817/1820 on the tunnel floor |
| `tunnel_wall` | 19 | corridor, stair-room and side-room walls |
| `door_lintel` | 4 | over the dead-end doorways |
| `tunnel_floor` | 133 | deep floor tiles with open tunnel space above (found from an open-space grid at y -3) |
| `tunnel_ceiling` | 137 | street slabs (y -1..0) with tunnel space below |
| `mall_link_floor` / `_ceiling` / `_wall` / `_bench` | 3 / 3 / 4 / 5 | MallStaticCollision pieces of the link (mall-owned colliders, listed for the tunnel look) |
| `mall_oval_wall_gap_lintel` | 4 | the entrance into the mall hall |
Also: `openings` (8 volumes that must stay empty to 2.05 m), `district_lights` (32), `panels` (214) — the last two
need builder requests R1/R2.

## What I added (visual only)
Works with today's builder (89 props):
- 22 **paper lanterns** hanging from the ceiling down the corridor, south branch, link and side rooms
  (bottom 3.32 m above the floor);
- 22 **wall lamps** on the corridor walls at 2.5 m, every 8 m, only where the wall is continuous (exact face found by
  a 1 cm solid search, 5 cm off it);
- 21 **posters** in triplets at eye level, 5 cm off the walls;
- 10 lit **way-finding light boxes** (station / mall / "mall B1" / side rooms / both stair rooms), bottom 2.25 m;
- **tactile dots** at both stair feet and at the mall entrance (flush).
Needs the builder patch (tested in preview):
- **tiles**: terracotta dado to 1.2 m + cream tiles above on every wall face (214 panels, 5 cm off the walls), dark warm
  ceiling panels, a yellow tactile guide line down the middle; R1;
- warm baked light pools under every lantern and at the signs; R2;
- tile role materials so the 0.35 m walls stop rendering as dark metal; R3.
- In `underground.tscn` (my own scene) `ambient_light_energy` is 0.4 instead of 0.65 so the standalone tunnel reads
  darker; R4 proposes the same for the full map.
Tried and dropped: plants in the dead corners (every tunnel floor counts as walkable).

## Test renders — `shots/underground_v0_<n>.jpg` (current shared builder) and `shots/underground_preview_<n>.jpg` (with R1–R3)
| # | Camera | Cloud draw calls v0 / preview |
|---|---|---|
| 1 | north stair foot, looking south down the corridor | 373 / 425 |
| 2 | corridor at the south side room, looking north | 170 / 223 |
| 3 | inside the north side room, looking west through the gap | 108 / 151 |
| 4 | south branch towards the mall (bench, "mall B1" sign) | 431 / 466 |
| 5 | street level at the north stair well, looking down the stairs | 381 / 433 |
| 6 | high view from the west into the south stair well | 542 / 597 |
Max 597 cloud draw calls in the high view (≈ 300–400 on Low), tunnel views 151–466: under 800.
`DISTRICT Underground: merged boxes into 25 meshes, quads into 6, 89 small props cast no shadow` (preview: 43 meshes), no SCRIPT ERROR.
**v0 honestly looks unfinished**: the walls of camera 3/4 render dark blue-grey (the builder's "thin = metal" rule) and the
tunnel is flat concrete; the preview shows what the requests give.

## Self-check (`python art_pass/districts/station/selfcheck.py underground [scene]`)
- 8 opening volumes (2 side-room gaps, 4 dead-end doorways, mall oval gap, corridor -> south branch), 2 flights, 4 landings
- current builder: **0 intrusions** (`selfcheck_result.json`); with R1–R3 applied: **0 intrusions**
  (`selfcheck_result_preview.json`; the first run found wall-tile panels on the sides of the ramps — fixed by keeping
  panels off every stair/landing footprint)
- 89 props: 54 at >= 2.05 m, 21 on walls (posters), 14 flush (tactile), **0 floor props**

## Known problems
- Today's builder: dark-metal tunnel walls, no tiles, no underground lights (R1–R3). This is the main open item.
- R4 (tunnel ambient) could not be verified in the cloud renderer.
- The side rooms' dead-end doorways show a bare slab face (nothing may go into the opening; I left them empty).
- The link and the mall's oval hall belong to the mall district; I stop panels at the oval wall (x -64.95).
- The skyline card bug (station R5) also shows in camera 6 from street level.

## Files
`underground_props.py` (generator; shared helpers in `../station/dresslib.py`), `UNDERGROUND_INVENTORY.json`,
`old_convex_hulls.json`, `underground.tscn`, `cameras.json`, `shots/`, `selfcheck_result*.json`, `BUILDER_REQUESTS.md`.
