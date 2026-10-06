# Station — builder requests (Claude, cloud, 2026-10-06)

The shared builder is not edited. Exact code for R1–R3 is in `../underground/BUILDER_REQUESTS.md` (one diff for both
districts, tested in this session on a scratch copy).

## R2 — `district_lights` at any height (needed here too)
`lights_in_or_affecting_region` only accepts `0.5 < y < 7`. The platform level is y 11–14, so the 5 lanterns under the
track canopy roof and the 2 lit shelter signs have no light. `STATION_INVENTORY.json` lists them as
`district_lights` (7 entries); the ground-level lamps (12) already work through the old key.

## R5 — skyline cards cut through the station (shared builder bug)
`slice_builder._skyline()` puts the near skyline cards on a 125 m circle around the world origin. The station is
~100–125 m from the origin (x -72..-120), so a card plane **passes through the station**: it is visible right behind the
north information island (camera 1) and the self-check finds it inside stair landing 909 at the street foot of the
north stair (`selfcheck_result.json`, `skyline_cards_crossing_volumes`). Proposal: let a district scene set the radii,
e.g. in `alley_builder.gd`
```gdscript
@export var SKYLINE_RADII := Vector2(125.0, 170.0)        # near, far; station/underground: Vector2(230, 280)
```
and use `SKYLINE_RADII.x / .y` instead of the literal 125.0 / 170.0 in `_skyline()` (override `_skyline()` in
`alley_builder.gd`, copying the loop, so `slice/*` stays untouched). In the full map the skyline should be placed
once for the whole map, outside the boundary walls (x -112 .. 92, z -84 .. 164).

## R6 — the express train has no dressing (game side)
`Gameplay/StationExpress2/ExpressCollision` is a moving `AnimatableBody3D` (3 cars 2.8 x 2.6 x 12 m on the east
track, x -79, y 11.23–13.83, driven by `station_train.gd`). A district builder only places static visuals, so the train
needs a mesh child on that body in the game scene (suggestion: `M_wall_concrete_4m`-style box per car with
`metal_panel` sides, a `window_room` quad strip and a `lamp_glow` headlight, so the lethal thing reads from far away).
Until then the danger is only marked by the dashed yellow warning line on the deck (42 rib tiles at x -82.9..-82.6).

## R7 — stair cheek walls that stand on a landing (shared `_structure_props`)
For every `stair_flight` the builder draws cheek walls 0.3 m outside the flight from `y_low - 0.3` to `tread + 0.3`.
Where a flight's foot lies on a landing (stair 904: its foot is on the turning landing 903 of the raised platform), the
lowest cheek boxes stand **on the landing walking surface** (self-check found them there). I set 904 to the role
`stair_flight_ramp` (drawn as its smooth ramp, no steps) to keep it clean. Proposal: skip a cheek box whose footprint
overlaps any `stair_landing` structure, then 904 can go back to `stair_flight`.

## R8 (optional) — the warning line as one panel
With R1 the 42 rib tiles of the express warning line can become one merged strip
(`{c: [-82.75, 11.005, 0], s: [0.3, 0.01, 144], mat: plaster_cream, tint: c69a3c}`), -40 draw calls on the platform views.
