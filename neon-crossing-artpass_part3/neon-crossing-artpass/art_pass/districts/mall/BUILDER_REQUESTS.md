# Mall: builder requests (for Claude main)

The mall runs on a thin district subclass, `districts/mall/mall_builder.gd`, which
`extends "res://art_pass/districts/alley/alley_builder.gd"`. No shared file was edited. The requests below move what
that subclass does into the shared builder. Once they are merged, `mall.tscn` can use `alley_builder.gd` directly and
`mall_builder.gd` can be deleted.

## 1. A district hook in `_build()` (needed, small)

**What:** add a no-op `_district_extras()` to `alley_builder.gd` and call it just before the merger.
**Why:** the mall has to add its dressing before `merge_boxes` runs, so the screen frames merge too. Right now the
subclass does this by overriding `_skyline()` and calling `super()`. That works, but it is a hack.

```gdscript
# alley_builder.gd, in _build(), replace
	_skyline()
	var merger = load("res://art_pass/districts/alley/merge_boxes.gd")
# with
	_district_extras()
	_skyline()
	var merger = load("res://art_pass/districts/alley/merge_boxes.gd")

# and add anywhere in the file
## Districts that need their own dressing override this (runs after the old layout + structures, before merging).
func _district_extras() -> void:
	pass
```
After this, rename `_skyline()` to `_district_extras()` in `mall_builder.gd` and remove its `super()` call.

## 2. Merge the convex-collider visuals (needed: this is the mall's draw-call fix)

**What:** a `merge_hulls(root, cell)` in `merge_boxes.gd`, called next to `merge()` and `merge_quads()`.
**Why:** `_old_layout()` creates one `MeshInstance3D` per convex collider. The mall has **3,207** of them (floor ring
segments, shop fronts, rails, roof ring). Merged per (material, 48 m cell), that becomes **16 meshes**. The flat
normals also fix a real visual bug: `_hull_mesh()` smooths normals, so each of the 128 ring segments shades as a
gradient (a fluted roof and outer wall, visible in v0 vs v1 of the renders). This would help every district with
convex colliders, not only the mall.

```gdscript
## merge_boxes.gd: convex / concave collider visuals ("Old<n>", ArrayMesh) -> one mesh per (material, cell),
## flat per-triangle normals (hull normals are smoothed, which shades ring segments as gradients).
static func merge_hulls(root: Node3D, cell := 48.0) -> int:
	var groups := {}
	for mi in root.get_children():
		if not (mi is MeshInstance3D) or not str(mi.name).begins_with("Old"):
			continue
		var mesh: Mesh = mi.mesh
		if not (mesh is ArrayMesh) or mi.material_override == null:
			continue
		var t: Transform3D = mi.transform
		var key := "%d|%d|%d" % [mi.material_override.get_instance_id(), floori(t.origin.x / cell), floori(t.origin.z / cell)]
		if not groups.has(key):
			groups[key] = {"mat": mi.material_override, "pos": PackedVector3Array(), "nor": PackedVector3Array()}
		var arr := mesh.surface_get_arrays(0)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var vn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var idx = arr[Mesh.ARRAY_INDEX]
		var order := PackedInt32Array()
		if idx is PackedInt32Array and (idx as PackedInt32Array).size() > 0:
			order = idx
		else:
			order.resize(v.size())
			for k in v.size():
				order[k] = k
		var pos: PackedVector3Array = groups[key].pos
		var nor: PackedVector3Array = groups[key].nor
		for k in range(0, order.size(), 3):
			var a := t * v[order[k]]
			var b := t * v[order[k + 1]]
			var c := t * v[order[k + 2]]
			var fn := (c - a).cross(b - a)
			if fn.length_squared() < 1e-12:
				continue
			fn = fn.normalized()
			if vn.size() == v.size() and fn.dot(t.basis * (vn[order[k]] + vn[order[k + 1]] + vn[order[k + 2]])) < 0.0:
				fn = -fn
			pos.append_array([a, b, c])
			nor.append_array([fn, fn, fn])
		groups[key].pos = pos
		groups[key].nor = nor
		root.remove_child(mi)
		mi.queue_free()
	var made := 0
	for key in groups:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = groups[key].pos
		arrays[Mesh.ARRAY_NORMAL] = groups[key].nor
		var am := ArrayMesh.new()
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var out := MeshInstance3D.new()
		out.name = "MergedHulls_%d" % made
		out.mesh = am
		out.material_override = groups[key].mat
		out.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		root.add_child(out)
		made += 1
	return made
```
and in `alley_builder.gd` `_build()`, after `var quads: int = merger.merge_quads(_root, 48.0)`:
```gdscript
	var hulls: int = merger.merge_hulls(_root, 48.0)
```
Note: the `children of _root` scan is on purpose. `_old_layout()` adds the `Old<n>` nodes directly under `_root`.

## 3. Lightmap UV2 for the merged hulls (wanted before the bake; not blocking the PR)

**What:** give the merged hull meshes a UV2 so they can be `GI_MODE_STATIC` and baked.
**Why:** the mall's promenade floors, shop fronts, rails and roof are all convex colliders. Without UV2 they are lit by
light probes only, while the box-merged parts get baked light. In the bake, the floors and the shop-front glass base will
read flatter than the boxes next to them.
**Proposal:** group each hull's triangles by face plane (the hull's own faces, from `old_convex_hulls.json`), then
shelf-pack each face's 2D bounds the same way `merge_boxes._build()` packs box faces (`TEXELS = 6`, `PAD = 2`). The
mall's ~3,200 hulls have ~6–8 faces each, so this is about 25k rects, the same order as the box merge. If that is too
slow at load time, the fallback is `ArrayMesh.lightmap_unwrap()`, which works in the editor only, at bake time. The
runtime then needs the baked UV2 saved, which the current "build at runtime" approach does not do, so the face packer
is the better option.

## 4. Mall roles in the shared `_role_mat()` (nice to have)

**What:** move the `match role` table from `mall_builder.gd` `_role_mat()` into `alley_builder.gd` `_role_mat()`.
These roles: floor_slab, plaza, outer_wall, shop_ceiling, roof, atrium_curb, atrium_rail, facade_sill, mullion,
column, escalator_handrail, roof_bridge, mast, misc, entrance_canopy, atrium_platform, escalator,
escalator_balustrade, promenade_furniture, shop_fixture, cafe_fixture, underground, basement_wall, shop_front,
facade_glass. Plus the `_tri()`, `_flat()` and `_glass()` helpers.
**Why:** the table is useful to every district, and one copy keeps the materials consistent (the whole-map limit is ≤ 40
unique materials).

## 5. `SKIP_ROLES` export (nice to have)

**What:** `@export var SKIP_ROLES: Array[String] = []`, and in `_old_layout()` skip the visual (not the collision) when
`str(_roles.get(idx, "")) in SKIP_ROLES`.
**Why:** the mall's basement (roles `underground`, `basement_wall`, `cafe_fixture`, 461 colliders below the atrium,
floor at −5) belongs to the underground district, per REGIONS.json. For now the mall draws them in plain concrete so the
atrium does not look bottomless. Once the underground district exists, the mall scene would set
`SKIP_ROLES = ["underground", "basement_wall", "cafe_fixture"]`.
