# Underground — builder requests (Claude, cloud, 2026-10-06)

The shared builder (`alley_builder.gd`) is not edited. Everything below is a proposal for Claude (main) to merge.
All of it was tested on a scratch copy of the builder in this session: preview renders `shots/underground_preview_*.jpg`,
self-check with the patch applied: 0 intrusions (`selfcheck_result_preview.json`).
`UNDERGROUND_INVENTORY.json` already carries the data (`panels`, `district_lights`, roles); the current builder ignores it.

## Why
With today's builder the tunnel renders badly (`shots/underground_v0_*.jpg`):
- the tunnel walls are 0.35 m thick (0.3499 after float rounding), so `_old_layout` gives them the **dark blue-grey
  "thin = metal" material** — they read as holes in the wall (v0 cameras 3, 4);
- the slab faces that bound most of the tunnel are plain concrete, floors and ceiling too: no tiles, no "station
  underpass" read;
- lights are only taken from `lights_in_or_affecting_region` with `0.5 < y < 7`: **no lamp can exist underground
  (y -5..-1)** nor at platform level (y 11..14).

## R1 — district `panels` (thin visual boxes)
What: an inventory list `panels: [{c: [x,y,z], s: [sx,sy,sz], mat: <TILING name>, tint: "rrggbb", uv: <triplanar scale>}]`,
built as `BoxMesh` + material override + static GI, so `merge_boxes` folds them into a handful of meshes
(underground: 214 panels -> +18 merged meshes, +40..55 cloud draw calls in the tunnel views).
Used for: wall tiles 2 cm thick, **5 cm off every tunnel wall face** (terracotta dado to 1.2 m, cream tiles above),
ceiling panels 5 cm under the slabs (dark warm metal), the yellow tactile guide line down the corridor.
Generated from the open-space grid of the tunnel; panels never enter an opening volume or a stair/landing footprint
(`underground_props.py`: `hits_opening`, `hits_stair`), and stop at the mall's oval wall.

## R2 — `district_lights` at any height
What: `district_lights: [{p: [x,y,z], col: "rrggbb", e: energy, r: range}]` -> `_light()` (baked, hidden at runtime by
`_runtime_cost_cuts` like every other lamp). Underground: 22 lantern lights (ffb867, 1.2, 6 m) + 10 sign spills.
Station uses the same key for the platform level (see `../station/BUILDER_REQUESTS.md`).

## R3 — role materials for the tunnel
`tunnel_wall`, `door_lintel`, `mall_link_wall` -> cream tiles (paving_stone, 1 m triplanar, f1e6d2);
`tunnel_floor`, `mall_link_floor` -> floor tiles (paving_stone, 1 m, warm grey). Fixes the dark-metal walls even
where no panel covers them. `tunnel_ceiling` deliberately gets **no** role material: those slabs' top face is the
station street (y 0), the ceiling look comes from R1 panels instead.

### Exact code (R1 + R2 + R3), unified diff against today's `alley_builder.gd`
```diff
--- a/art_pass/districts/alley/alley_builder.gd
+++ b/art_pass/districts/alley/alley_builder.gd
@@ -55,6 +55,8 @@
 	_street()
 	if not _roles.is_empty():
 		_structure_props()
+	if inv.has("panels"):
+		_panels()
 	_skyline()
 	var merger = load("res://art_pass/districts/alley/merge_boxes.gd")
 	var merged: int = merger.merge(_root, 48.0)
@@ -212,6 +214,14 @@
 		"pavilion_roof":
 			var r := _tiling("roof_kawara") as StandardMaterial3D
 			r.uv1_triplanar = true; r.uv1_world_triplanar = true; r.uv1_scale = Vector3(0.5, 0.5, 0.5); m = r
+		"tunnel_wall", "door_lintel", "mall_link_wall":                 # R3: cream tiles, never the dark 'thin = metal' look
+			var t := _tiling("paving_stone") as StandardMaterial3D
+			t.uv1_triplanar = true; t.uv1_world_triplanar = true; t.uv1_scale = Vector3(1, 1, 1)
+			t.albedo_color = Color("f1e6d2"); m = t
+		"tunnel_floor", "mall_link_floor":
+			var f := _tiling("paving_stone") as StandardMaterial3D
+			f.uv1_triplanar = true; f.uv1_world_triplanar = true; f.uv1_scale = Vector3(1, 1, 1)
+			f.albedo_color = Color(0.78, 0.74, 0.72); m = f
 		"hill_surface":
 			var h := _tiling("plaster_cream") as StandardMaterial3D        # moss + grass: green tint over a soft texture
 			h.uv1_triplanar = true; h.uv1_world_triplanar = true; h.uv1_scale = Vector3(0.25, 0.25, 0.25)
@@ -263,6 +273,31 @@
 		place(node, str(p.piece), Vector3(p.pos[0], p.pos[1], p.pos[2]), float(p.rot))
 
 
+## R1 (station/underground): thin visual boxes listed by the district (wall tiles 5 cm off the walls, ceiling
+## panels, guide lines). BoxMesh + material_override + static GI, so merge_boxes folds them into a few meshes.
+var _panel_mats := {}
+func _panels() -> void:
+	var node := Node3D.new()
+	node.name = "Panels"
+	_root.add_child(node)
+	for p in inv.panels:
+		var key := "%s|%s|%s" % [p.mat, str(p.get("tint", "")), str(p.get("uv", 0.5))]
+		if not _panel_mats.has(key):
+			var m := _tiling(str(p.mat)) as StandardMaterial3D
+			m.uv1_triplanar = true; m.uv1_world_triplanar = true
+			var uv := float(p.get("uv", 0.5)); m.uv1_scale = Vector3(uv, uv, uv)
+			if p.has("tint"):
+				m.albedo_color = Color(str(p.tint))
+			_panel_mats[key] = m
+		var mi := MeshInstance3D.new()
+		var bm := BoxMesh.new(); bm.size = Vector3(p.s[0], p.s[1], p.s[2]); bm.add_uv2 = true
+		mi.mesh = bm
+		mi.material_override = _panel_mats[key]
+		mi.position = Vector3(p.c[0], p.c[1], p.c[2])
+		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
+		node.add_child(mi)
+
+
 func _local_aabb(s: Dictionary, mesh: Mesh) -> AABB:
 	if str(s.type) == "convex":
 		var pts := _pts(s.points)
@@ -523,6 +558,9 @@
 	# overhead cables across the main lane and lamps along it, all above head height
 	for c in CABLES:
 		place(_root, "P_cable_bundle_6m", c, 90)
+	for l in inv.get("district_lights", []):          # R2 (station/underground): baked lamps at any height
+		_light("DLamp_%d" % _count, Vector3(l.p[0], l.p[1], l.p[2]), Color(str(l.col)), float(l.e), float(l.r))
+		_count += 1
 	for l in inv.get("lights_in_or_affecting_region", []):
 		var p := Vector3(l.position[0], l.position[1], l.position[2])
 		if p.y > 0.5 and p.y < 7.0 and REGION.has_point(Vector2(p.x, p.z)):
```
(The preview copy also overrode `_runtime_cost_cuts()` to keep the lamps live in the unbaked cloud render; that is
**not** part of the request.)

## R4 — darker ambient inside the tunnel (UNTESTED here)
The environment's ambient is a flat colour (`ambient_light_source = 3`, energy 0.65), so the tunnel gets the same
ambient as the street: it can never feel dark. In the standalone `underground.tscn` I lowered `ambient_light_energy`
to 0.4 (my own scene only). For the full map I propose an interior `ReflectionProbe` with an ambient override:
```
[node name="TunnelAmbient" type="ReflectionProbe" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -78, -3, 8)
size = Vector3(34, 4.4, 160)
interior = true
ambient_mode = 2
ambient_color = Color(0.42, 0.3, 0.24, 1)
ambient_color_energy = 0.5
```
It made **no visible difference in the cloud's gl_compatibility renderer** (mean luminance 82.3 vs 82.0), so it needs a
test on Nizar's PC renderer before anyone relies on it. After the bake the lightmap should carry most of the darkness
anyway (the sun cannot reach the tunnel).
