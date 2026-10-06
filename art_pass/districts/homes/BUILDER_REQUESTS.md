# HOMES: builder requests (Claude, cloud, 2026-10-06)

Four small changes to the shared `art_pass/districts/alley/alley_builder.gd`, all **data-driven**: each one does nothing
unless an inventory sets the new field, so alley / shrine / crossing build exactly as before.
The exact code is in `builder_requests.patch` (unified diff against the current builder, from the project root:
`git apply art_pass/districts/homes/builder_requests.patch`). I tested it locally without committing it: both districts
build with no script errors, and the self-check results are in REPORT.md. The park needs R2 only
(`districts/park/BUILDER_REQUESTS.md`).

## R1: no roof antenna on roofs that are routes
**What:** `_dress()` puts a `P_roof_antenna` (2.5 × 2.2 × 3 m) on every roof above 8 m. Skip it when the building has
`"roof_is_route": true`.
**Why:** homes roofs are parkour routes. The current builder puts antennas on 7 of the 10 roofs (A1, A2, A3, V2, V3, V6,
V7), all inside the walkable roof volume. The self-check reports these 7 as WALKABLE TOP intrusions with the
current builder.
```gdscript
	if H > 8.0 and not bool(b.get("roof_is_route", false)):     # R1 (homes): roofs that are routes stay clear
		place(node, "P_roof_antenna", Vector3(cx + w * 0.5 - 0.4, H, cz - d * 0.5 + 0.4))
```

## R2: flat ground patches (lawns, paved paths)
**What:** a new inventory list `ground_patches: [{rect_xz: [x0, z0, x1, z1], top_y, mat: "lawn" | "paving", thick}]`.
The builder turns each patch into a plain BoxMesh with `material_override`, GI static and no collision. `merge_boxes`
then merges the patches like the cladding: homes goes from 27 to 33 merged meshes, park from 26 to 30. Lawn reuses the
shrine's `hill_surface` role material, so there is no new material, texture or shader. Paving uses the street paving material.
**Why:** the old homes and park are flat. The lawns (garden plots, the residential green, the two park lawns) had no
collision. With the current builder, they can't be shown without placing hundreds of tiles (one draw call each).
Patch tops sit ≤ 1.2 cm above the old ground (top y 0). Backdrop patches beyond the boundary walls are 0.6 m thick, so
the treeline stands on ground.
```gdscript
	_street()
	_ground_patches()
	if not _roles.is_empty():
```
```gdscript
## R2 (homes, park): flat ground skins from the inventory, e.g. lawns and paved paths on the old flat ground.
## "ground_patches": [{"rect_xz": [x0, z0, x1, z1], "top_y": 0.012, "mat": "lawn" | "paving", "thick": 0.02}]
## Plain boxes (merged by merge_boxes into a few meshes), top <= 1.2 cm above the old ground, no collision.
func _ground_patches() -> void:
	var patches: Array = inv.get("ground_patches", [])
	if patches.is_empty():
		return
	var node := Node3D.new()
	node.name = "GroundPatches"
	_root.add_child(node)
	var paving := _tiling("paving_stone") as StandardMaterial3D
	paving.uv1_triplanar = true; paving.uv1_world_triplanar = true; paving.uv1_scale = Vector3(0.5, 0.5, 0.5)
	paving.albedo_color = Color(0.84, 0.87, 0.97)
	for p in patches:
		var r: Array = p.rect_xz
		var t := float(p.get("thick", 0.02))
		var size := Vector3(float(r[2]) - float(r[0]), t, float(r[3]) - float(r[1]))
		var mi := MeshInstance3D.new()
		mi.name = "Patch%d" % node.get_child_count()
		var bm := BoxMesh.new(); bm.size = size; bm.add_uv2 = true
		var side := clampi(int(sqrt(size.x * size.z) * 4.0), 16, 512)
		bm.lightmap_size_hint = Vector2i(side, side)
		mi.mesh = bm
		mi.material_override = _role_mat("hill_surface") if str(p.get("mat", "lawn")) == "lawn" else paving
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		mi.position = Vector3((float(r[0]) + float(r[2])) * 0.5, float(p.get("top_y", 0.01)) - t * 0.5, (float(r[1]) + float(r[3])) * 0.5)
		node.add_child(mi)
```

## R3: cornice depth per building
**What:** `_cornice()` takes a `depth` (default 0.28 m, unchanged). `_dress()` passes the building's
`cornice_depth` when the inventory sets one. Homes sets 0.12 m, and 0.11 m (flush with the cladding) on the three
buildings with an R4 plain face (A2, V1, V1 wing). A shallow cornice also overhangs the corners by its depth
instead of 0.25 m. Default buildings keep 0.28 / 0.25 exactly.
**Why:** the outdoor service flights run 0.1–0.3 m from the west walls of A1–A3 and V1–V7 (route corridors from the
dump, 1.25 m wide). A 0.28 m cornice at roof height pokes 2–6 cm into the A2, V2, V3 and V7 flight corridors at head
height, where the flight reaches the roof (self-check, current builder). Its 0.25 m corner overhang reaches into the
V1 flight where the flight runs past the end of the house.
```gdscript
		_cornice(node, n, plane, fc[2], fc[3], H, trad, float(b.get("cornice_depth", 0.28)))     # R3 (homes): shallow next to flights
```
```gdscript
func _cornice(node: Node3D, n: Vector3, plane: float, u0: float, u1: float, H: float, trad: bool, depth := 0.28) -> void:
	var ext := 0.25 if depth >= 0.28 else depth              # R3: a shallow cornice also overhangs the corners less
	_face_box(node, n, plane, (u0 + u1) * 0.5, H - 0.45, u1 - u0 + 2.0 * ext, 0.42, depth, "roof_kawara" if trad else "metal_panel", 0.0)
```

## R4: plain faces (no upper-floor windows)
**What:** a building may list `"plain_faces": [[nx, nz], ...]`. Faces with those normals get cladding and cornice
but no upper-floor windows (frames stick out 0.19 m). `make_inventory.py` lists a face only where a service-flight
corridor passes less than 0.2 m from it. Today that is the west face of V1, of its garden wing, and of A2 (gap 0.195 m: frames would clear the corridor by 5 mm).
**Why:** V1's upper flight runs 0.1 m from the west wall (dump route corridor edge x 25.695, wall x 25.8), so window frames
there would sit 9 cm inside the flight volume, between knee and head height. CLAUDE.md rule 2 says nothing inside a
stair volume up to +2 m. The other eight houses' flights are 0.25–0.6 m from their walls and keep their windows.
```gdscript
		var plain := false                                     # R4 (homes): no windows on "plain_faces" (flights 0.1 m off the wall)
		for pf in b.get("plain_faces", []):
			if Vector3(float(pf[0]), 0, float(pf[1])).dot(n) > 0.9:
				plain = true
		var lv := 1
		while lv * 3.1 + 2.6 < H and not plain:
```

## Not requested (worked around in data)
- Ivy on the apartment blocks hung over the balconies and one flight: homes uses the kind `apartment_block` (plain),
  not `apartment`, so the builder adds no ivy.
- Traditional dressing (eaves at 3.3 m, porch posts, noren) would cover the 3.3–3.6 m balconies: homes uses no TRAD kinds.
- The builder's cladding (5 cm gap + 6 cm board, outer face 11 cm off the wall) overlaps the outer 1 cm of the V1–V7
  flight hulls, which run 10 cm from the wall. That is the standard cladding of every district, so no request. The
  self-check allows it explicitly (12 cm wall skin inside flight volumes).
