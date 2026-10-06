# GROUND PASS: report (Claude, cloud, 2026-10-06)

Before this pass every street was one flat paving colour. Every district now has `districts/<d>/GROUND_DETAIL.json`:
asphalt on the drivable / central street areas, paving left along the building faces, stone kerb lines at the road
edge, the scramble crossing painted (4 crosswalks + the X, stop lines, centre lines), edge lines, and manholes, drain
covers, repair patches and puddle marks scattered on the road. It is visual data only: no collision, no layout
change, and no shared file edited. The builder code that draws it is a request
(`GROUND_BUILDER_REQUEST.md` / `.patch`). It was tested on a scratch working copy and reverted.

## Files
| File | What |
|---|---|
| `art_pass/tools/inventory/ground_probe.py` | Top-down height field of the old collision per 10 cm cell (5 cm in the check). Gives the ground-slab top, anything standing in the 2.2 m column above it, and the lowest cover above head height. Box/convex shapes are solved exactly from their half-spaces; concave shapes (stair flights, hill) are rasterised. |
| `art_pass/tools/inventory/ground_detail.py` | The generator: `python tools/inventory/ground_detail.py [district ...] [--preview DIR]` (from `art_pass/`). Deterministic (seed per district). |
| `art_pass/tools/inventory/ground_check.py` | Independent self-check, re-run on the JSON (below). Exit 1 on any failure. |
| `districts/<d>/GROUND_DETAIL.json` | Per district: 6 materials, items `[mat_id, cx, cz, sx, sz, top_y, yaw]`, stats. |
| `districts/<d>/GROUND_SELF_CHECK.json` | Self-check result per district. |
| `districts/GROUND_BUILDER_REQUEST.md` / `.patch` | Builder request G1: `_ground_detail()`, +44 lines, data-driven. |
| `districts/ground_renders/` | Before/after renders (2 per district), top-down plans, `draw_calls.json`, the ground review cameras (`cams/`). |

## How the ground is classified (from the old collision, not by hand)
1. **Street** = a cell over the old ground slab (a flat box whose top is the district level: y 0, underground y -5),
   with nothing in the column from +3 mm to +2.2 m and no cover lower than 6 m (station: no cover at all;
   underground: its own 4 m tunnel ceiling is allowed). Then it is shrunk by:
   - 0.3 m from anything standing on the ground;
   - 1.0 m around doorways (covered walkable cells that touch open street, e.g. lintels and arcade mouths);
   - building footprints +0.2 m;
   - opening prisms 1 m in front;
   - stair / landing / terrace / ramp / escalator volumes +0.5 m;
   - lawns and paths (`ground_patches`), floor panels, and ground props (drain grates, tactile tiles) +0.15 m.
2. **Road (asphalt)** = street cells at least *side* metres (chessboard distance) from the street edge, opened by a
   square of the minimum road width. Pieces under 40 m² are dropped. Small islands (< 8 m², e.g. signal poles or the
   bench in the scramble) don't push the road back. The rest of the street stays the old paving, which becomes the
   pavement along the building faces.
   Parameters per district (side / min width): crossing 2.0 / 4.0 m, mall 3.0 / 6.0 m, station 2.0 / 4.5 m,
   alley 2.2 / 3.0 m, homes 1.0 / 3.0 m (Japanese residential lanes are asphalt almost wall to wall).
   Shrine, park and underground have **no asphalt**: shrine grounds and park stay stone, and the tunnel keeps its tiles.
3. **Kerb** = a 20 cm granite strip on the pavement side of every road edge.
4. **Paint**:
   - **Scramble crossing** (crossing district). The intersection box is x -12..1, z -16..-2, the open plaza between the
     north / south streets and the west / east openings, where the old map drew its X (the old map centre was about
     x -7, z -5). It has four crosswalks (0.45 m bars, 0.45 m gaps, 4 m deep, clipped to the kerbs). The two
     diagonals are rotated 45° and cross corner to corner; the second diagonal leaves the centre to the first, so
     nothing overlaps. Stop lines sit 2 m behind the crosswalks on the incoming (left-hand-traffic) half. Centre
     lines run from the stop lines: solid for 8 m, then dashed.
   - **Edge lines**: 20 cm, 0.5 m in from the kerb, on roads at least 3.5 m wide. They are cut out around the scramble.
5. **Spots** (layer 3, never on paint, fully on the road / paving; 0.3 m clear of other spots, puddles 0.2 m):
   - manholes: a round 0.7 m lid built from 3 disjoint boxes;
   - drain covers: 0.4 × 0.8 m along the kerb on the road side, ≥ 2 m apart, about one per 10 m of kerb. Underground:
     along the tunnel walls;
   - repair patches: rectangles of duller asphalt;
   - puddle marks: blobs from 3 ellipses, cut into disjoint boxes.

## Height and z-fighting
| Layer | Top above old ground | Contents |
|---|---|---|
| 1 | +0.7 cm | asphalt, kerb strips (side by side, never overlapping) |
| 2 | +1.3 cm | road paint |
| 3 | +1.9 cm | manholes, drain covers, patches, puddles |

Every box is 1 cm thick, so it sinks 3 mm below the old ground at most, and its top is 0.7–1.9 cm above it. There are
no kerb steps and no collision is ever added. Layers are 6 mm apart and same-layer boxes never overlap, so any
overlap is between different layers (a stripe on asphalt).

## Results
| District | Asphalt m² | Street m² | Kerb boxes | Crosswalk stripes | Stop / centre / edge line boxes | Manholes | Drain covers | Patches | Puddles | Boxes | Meshes | Self-check |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alley | 569 | 1731 | 41 | 0 | 0/0/0 | 7 | 18 | 9 | 8 | 181 | 6 | OK |
| crossing | 4254 | 6553 | 224 | 60 (43 straight + 17 diagonal) | 3/4/120 | 19 | 60 | 25 | 21 | 931 | 23 | OK |
| shrine | 0 | 1691 | 0 | 0 | 0/0/0 | 4 | 0 | 0 | 6 | 83 | 2 | OK |
| mall | 262 | 1348 | 13 | 0 | 0/0/5 | 1 | 8 | 1 | 1 | 46 | 17 | OK |
| station | 991 | 2546 | 66 | 0 | 0/0/49 | 4 | 31 | 5 | 5 | 248 | 21 | OK |
| underground | 0 | 1101 | 0 | 0 | 0/0/0 | 2 | 24 | 0 | 2 | 51 | 3 | OK |
| homes | 2601 | 3731 | 71 | 0 | 0/0/32 | 13 | 59 | 16 | 13 | 394 | 11 | OK |
| park | 0 | 1829 | 0 | 0 | 0/0/0 | 3 | 0 | 0 | 4 | 49 | 3 | OK |

Box counts per paint type are rectangles after cutting a line into disjoint pieces, not separate markings.
*Meshes* is the number after merging per (material, 96 m cell) for the whole district; a view draws only the visible ones.

### Self-check (`python tools/inventory/ground_check.py`): 8 / 8 OK
On a fresh 5 cm probe, every 5 cm sample of every box (rotated diagonals included) must:
- have its top between +0.5 and +2.0 cm (actual range 0.7–1.9 cm);
- sit over the flat old ground slab (±1 mm), so never on a ramp, step, landing, roof or terrace;
- keep ≥ 0.25 m from any collider standing on the ground;
- not be covered by anything below 6 m (no interiors, arcades or lintels);
- not touch stair / landing / terrace / ramp / escalator volumes, building footprints, openings (1 m in front), lawns
  and paths, floor panels or ground props.

Same-layer boxes must not overlap, and boxes in different layers must be ≥ 5 mm apart.
I checked that the checker catches mistakes by injecting bad boxes into a copy of the crossing file: one on ramp 1794,
one inside tower C01, one 2.5 cm high, one overlapping in the same layer, and one on the scramble bench. It reported
all 5 (`height` 1, `obstacle` 3, `volumes` 1, `overlap` 1).
The repo's doorway check (`art_pass/tools/check_openings.gd`) with the patched builder reports 0 intersections in
all 8 districts (alley 20 openings, crossing 54, station 8).

### Draw calls (cloud gl_compatibility, no bake; the cloud count is about 1.5–2× the real Low count)
Builder patched vs current builder, same cameras (`ground_renders/draw_calls.json`):
| District | 6 district cameras: before → after | Δ | Ground cameras Δ |
|---|---|---|---|
| alley | 612/658/510/579/598/454 → 618/664/516/585/604/460 | +6 | – |
| crossing | 411/424/402/262/473/541 → 432/445/424/283/495/564 | +21..23 | – |
| shrine | 74/84/83/72/79/75 → 76/86/84/74/80/77 | +1..2 | +2 |
| mall | 206/271/212/176/215/128 → 223/286/220/182/228/145 | +6..17 | +6..14 |
| station | 212/304/242/301/220/277 → 216/319/257/316/235/298 | +4..21 | +12..15 |
| underground | 293/223/150/124/303/310 → 296/226/151/126/306/313 | +1..3 | +3 |
| homes | 214/148/220/212/180/190 → 220/154/226/223/186/201 | +6..11 | – |
| park | 221/301/275/309/303/274 → 221/304/276/312/306/277 | +0..3 | +2 |

The worst view is crossing cam 6 at 564 cloud draw calls, still under the 800 budget even before the cloud-to-Low
discount. The ground meshes cast no sun shadow, so the shadow pass costs nothing extra.

## Renders (`districts/ground_renders/`, before | after side by side)
- alley `cam5`, `cam6`; crossing `cam3`, `cam4`; homes `cam1`, `cam2`. These are the district cameras with the most
  visible ground.
- shrine, mall, station, underground, park: their 6 district cameras barely see the ground (< 1 % of pixels change),
  so each has 2 eye-level **ground cameras** (`cams/<d>.json`). They stand on decorated street and look along it.
  They are placed automatically, except the underground pair, which I set by hand in the main corridor.
- `plan_<d>.png`: top-down plan. Dark = asphalt, white = paint and kerbs, blue = iron, violet = patches,
  cyan = puddles, beige = street paving, red = old collision, grey = excluded. Outside the district is dimmed.
  `plan_crossing_scramble.png` is a closer crop of the scramble with a 5 m grid.

## Known issues / for review
- **Kerb jogs.** Kerbs and edge lines follow building set-backs, so the road edge jogs by 0.5–1.5 m where a facade
  steps (crossing cam 3 / cam 4). A filter that straightens them without deleting narrow roads at their junctions
  needs more work; I left the jogs rather than risk gaps.
- **The bench in the middle of the scramble** (old collider 4046 at x -3, z -12) stays. It is an unpainted island
  0.3 m wide around the bench, and the X stripes stop there.
- **Shrine, park and underground are sparse on purpose** (stone grounds and a tiled tunnel: only manholes, puddles, and
  drain covers in the tunnel). Alley lanes are under 7 m wide, so they keep their stone and get spots. Only the street
  along the alley's south edge is asphalt.
- Mall and station have 17 / 21 ground meshes because their regions straddle the 96 m merge-cell lines (x 0 / z 0).
  A view only draws the cells it sees (+6..21 calls measured).
- Puddles use `plaster_cream` (smooth) tinted dark. The asphalt grain sparkled at low roughness. Cloud renders have no
  reflections or bake, so the wet look must be judged after Nizar's bake.
- The cloud renders show the same `ERR_CANT_OPEN` line before and after this pass. It is not from the ground pass.

## Builder request
See `GROUND_BUILDER_REQUEST.md`: one function `_ground_detail()` and one call after `_ground_patches()`. It reads
`GROUND_DETAIL.json` from the inventory's folder, so no scene edits are needed and a district without the file builds
as before.
