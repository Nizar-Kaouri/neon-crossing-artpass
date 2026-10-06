# District: MALL — report (Claude, cloud, 2026-10-06)

Region `[-72, 30, 2, 125]` (REGIONS.json). 4,982 old colliders have their AABB centre in it (4,679 above ground +
303 underground). One body, `MallStaticCollision`, holds 4,175 of them (3,193 convex, 982 boxes).
**Layout untouched:** this pass adds no collision and does not move, resize or remove any. Every collider is drawn as
its own shape with a role material.

## What the old mall is (from the dump)
- An oval, centre (−35, 81), semi-axes 30 × 48 m. Three promenade floors at **y 0 / 5.5 / 11** around an **open atrium**
  (open to the sky, down to a basement floor at −5, which is the underground district).
- A closed shop ring (ellipse radius 0.74–0.99) behind a continuous shop-front wall, 3.84 m per storey.
- The outer wall has two glass rows (y 0.8–3.3 and 6.3–8.8) with mullions. It stops at **11.95**: a 0.95 m parapet over
  the top floor is the **jump-out edge**. A roof ring at 15 sits over the top-floor shops.
- Three 48 m **travelators** (ramps with glass balustrades and handrails) cross the atrium and link −5 → 0, 0 → 5.5 and
  5.5 → 11. The atrium also has 7 parkour platforms at y 5.1, a roof bridge at 15 and 2 columns. There is no stepped
  stair in the mall: the stair-like boxes are rail posts and sloped handrails.
- Entrances (gaps in the outer wall): N (164–196°, plus two cream entrance portals), S (338–22°), E and W
  (84–96° / 264–276°, under a 3.3 m lintel), and N and S again on level 1.

## What I built
| File | |
|---|---|
| `MALL_INVENTORY.json` | 4,982 `structures`, one role each (counts in `role_counts`), plus `openings` (9), `stair_volumes` (23 travelator parts), and `dressing` (signs, screens, trims, lights) |
| `tools/mall_inventory.py` | Makes the inventory. Roles come from the height band + ellipse radius + size; checked against top-down plots of every height band |
| `old_convex_hulls.json` | `tools/convex_hulls.py -72 30 2 125` → 3,207 hulls |
| `mall.tscn` | A copy of crossing.tscn. INV / HULLS / REGION `Rect2(-72, 30, 74, 95)` / cameras; builder = `mall_builder.gd` |
| `mall_builder.gd` | A thin subclass of the shared builder (see BUILDER_REQUESTS.md): role materials, hull merge, dressing |
| `cameras.json` | 6 cameras. #3 is **inside the atrium** |
| `tools/self_check.py` | The doorway / stair / walkable check. It PASSES |
| `test_renders/` | The 6 renders (v2) |

**The slice's look, reused:**
- **Shop fronts** (432 convex walls) and **facade glass** (224 panels) use the slice's `mall_glass` shader: the painted
  shop strip, mapped by angle around the oval's centre, with lit / dim / closed bays and a sky fresnel. There are two
  instances, one tuned to the 3.84 m shop storey and one to the 2.52 m facade rows.
- The **cream plaster shell** (outer wall, shop-ceiling bands) and dark blue-grey metal mullions match the slice's
  `M_mall_band` and metal.
- **Two portrait screens** using the slice's `billboard.png` and `_screen()` material, 5 × 7.5 m, flush on the outer
  wall either side of the north entrance so they face the crossing, with thin metal frames. Their top is at 10.76, under
  the jump-out edge.
- **15 shop lightbox signs** from the `signs_horizontal` atlas, flush on the shop fronts at 2.75–3.55 m above each
  floor. All 15 are in **one mesh**: each quad's UV points at its own atlas cell, so there is no per-instance parameter.
- **Readability trim** (STYLE.md): light `#e8e2da` on the atrium curbs, rails and facade sills, plus 368 trim strips
  5 cm outside the roof ring's two edges and the parapet's outer face (the jump-out edges). All the trims are in one mesh.
- 27 baked lights: promenades, entrances, screen spill. As in every district, they are hidden live in the game.

## Draw calls (cloud renders, gl_compatibility, no bake: rough guide, cloud ≈ 1.5–2× real Low)
| Cam | What | Cloud draws |
|---|---|---|
| 1 | North forecourt, eye 1.7, looking into the north entrance | 200 |
| 2 | East street, eye 1.7, curved glass facade | 269 |
| 3 | **Inside the atrium**, ground-floor atrium edge, eye 1.7, looking north up all 3 floors | 209 |
| 4 | Level-1 promenade, eye 1.7: shop fronts, signs, travelator | 173 |
| 5 | Roof / top edge (y 15), looking over the atrium | 208 |
| 6 | High overview from the north-east | 121 |

The builder prints `DISTRICT mall: merged 3207 convex collider visuals into 16 meshes` and
`DISTRICT Mall: merged boxes into 47 meshes, quads into 8`. There is no SCRIPT ERROR. The worst cloud view is 269, so
the real Low count should be about 135–180, far under 800. Without the hull merge, the 3,207 convex visuals alone would
be over 3,200 draws.
New materials: about 16. The 25 roles share them, plus 2 `mall_glass` instances, the signs and the screen.

## Renders (`test_renders/`)
`mall_v2_1.jpg` … `mall_v2_6.jpg` = cameras 1–6 above. I looked at every image. v0 → v1 fixed fluted shading
(smoothed hull normals), dark atrium platforms (wrong role) and camera 4, which was inside a shop wall. v1 → v2 added
the cooler roof, the edge trims and metal masts.

## Self-check (`python districts/mall/tools/self_check.py`, run from `art_pass/`): PASS
Every added visual (15 signs, 2 screens with frames, 368 trims) is sampled on a 10 cm grid. Each sample point must be:
outside all 9 opening volumes (the entrances per floor, and the jump-out edge 11.95–14.0 all round); outside the 23
travelator volumes (+2 m); not free-standing below floor + 2.05 m (the 0.8 m facade sills count as floors); not inside
a collider; and ≥ 5 cm in front of the wall behind it.
The check caught three real problems, and I fixed all three before the PR:
1. The first screens cut through thin mullions.
2. The screen bottoms were 1 cm under a sill's 2.05 m clearance.
3. The first version put trims on the top-floor slab, which is inside the parapet.

## Known problems / limits
- **Merged hulls are not lightmapped** (probe-lit, `GI_MODE_DYNAMIC`, the same as the shared builder's hulls today).
  The floors, shop fronts and roof will look flatter after the bake than the box parts next to them. See
  BUILDER_REQUESTS #3.
- The roof deck still reads warm and pink under the low sun in the un-baked cloud renders, even after cooling the tint.
  Recheck it after the bake.
- `mall_glass` per-bay variation gives some long dim runs. In cam 2, the dark run on the lower row is the **open east
  entrance** (dark interior), not glass.
- The 617 `shop_fixture` colliders are inside closed shops and never visible. They are still drawn, merged into one
  timber mesh, so they cost triangles, not draw calls. A future `SKIP_ROLES` could drop them.
- The basement (461 colliders: `underground`, `basement_wall`, `cafe_fixture`) is drawn in plain concrete until the
  underground district dresses it (BUILDER_REQUESTS #5).
- No glass infill between the atrium curb and the handrail. The collision there is curb + rail with a 0.7 m gap, so
  glass would suggest a barrier that isn't there.
- Entrance openings were found by a ring scan at r 0.995. Where no lintel was found, the opening is counted up to the
  next floor. That is conservative: it keeps more space clear.
- Of 45 candidate sign spots, 15 were kept. The others were rejected because the wall behind them was not continuous.

## Builder requests
See `BUILDER_REQUESTS.md`:
1. A `_district_extras()` hook.
2. `merge_hulls()` with flat normals (this is the draw-call fix).
3. UV2 for merged hulls.
4. Mall roles in the shared `_role_mat()`.
5. A `SKIP_ROLES` export.

## Reproduce
```
cd art_pass && python districts/mall/tools/mall_inventory.py && python tools/convex_hulls.py -72 30 2 125 districts/mall/old_convex_hulls.json
python districts/mall/tools/self_check.py
cd .. && xvfb-run -a -s "-screen 0 1600x900x24" godot --rendering-driver opengl3 --path . res://render_cams.tscn -- --scene=res://art_pass/districts/mall/mall.tscn --cams=res://art_pass/districts/mall/cameras.json --out=renders/mall_v2
```
Repo note: this checkout stores the project in three part folders. The districts live in
`neon-crossing-artpass_part3/neon-crossing-artpass/`, so the mall folder is there too. To run it, overlay parts 1–3
into one folder.
