# GROUND PASS: builder request (Claude, cloud, 2026-10-06)

One small, data-driven addition to the shared `art_pass/districts/alley/alley_builder.gd`. It does nothing unless a
district folder holds a `GROUND_DETAIL.json` (next to its inventory), so a district without one builds exactly as before.
No change to `merge_boxes.gd`, the slice builder, the kit, shaders or the export. No scene needs editing: the file is
found from `INV.get_base_dir()`, which all 8 district scenes already set (alley uses the default INV path).

The exact code is also in `GROUND_BUILDER_REQUEST.patch` (unified diff against the current builder; from the project
root: `git apply art_pass/districts/GROUND_BUILDER_REQUEST.patch`). I tested it on a scratch copy only (patch applied in
the working tree, renders and checks run, patch reverted; the shared builder in this PR is unchanged).

## G1: `_ground_detail()` (asphalt, kerb lines, road paint, manholes, drain covers, repair patches, puddle marks)
**What:** read `<district>/GROUND_DETAIL.json` (made by `art_pass/tools/inventory/ground_detail.py`) and build its thin
boxes. The file carries its own materials (6, all from existing tiling textures: `asphalt` x3 tints, `paving_stone`
for kerbs, `plaster_cream` for paint, `metal_panel` for iron lids) so no new texture, shader or material resource is
needed. Boxes are merged per (material, 96 m cell) with merge_boxes' existing UV2 packer (`_build`), GI static
(lightmapped like the cladding), **no sun shadow** (a 1 cm skin casts nothing visible; this keeps the shadow pass free).
Meshes are `ArrayMesh`, so the later `merge()` / `merge_quads()` / `merge_hulls()` calls leave them alone.

**Why:** the builder only knows `ground_patches` (lawn / paving, one material each and no rotation); roads need
asphalt, paint, iron and rotated stripes (the scramble's diagonals), and ~50-930 boxes per district want their own
shadow-free merge rather than joining the shadow-casting cladding groups.

**Safety (all enforced by the generator and re-tested by `tools/inventory/ground_check.py`):** tops 0.7 / 1.3 / 1.9 cm
above the old ground, no collision, never on stairs / landings / ramps / roofs / in buildings or doorways, no overlap
inside a layer, layers 6 mm apart.

Call it right after the ground patches in `_build()`:
```gdscript
	_street()
	_ground_patches()
	_ground_detail()
	if not dress_data.is_empty():
```
and add the function (e.g. after `_ground_patches()`):
```gdscript
## GROUND PASS: flat ground detail from <district>/GROUND_DETAIL.json next to the inventory (made by
## tools/inventory/ground_detail.py): asphalt, kerb lines, road paint, manholes, drain covers, repair patches, puddles.
## Item = [mat_id, centre_x, centre_z, size_x, size_z, top_y, yaw_deg]: a thin box whose top sits 0.7 / 1.3 / 1.9 cm above
## the old ground. Visual only, no collision. One mesh per (material, merge_cell) through merge_boxes' UV2 packer,
## lightmapped (GI static), no sun shadow. Districts without the file build exactly as before.
func _ground_detail() -> void:
	var path := INV.get_base_dir().path_join("GROUND_DETAIL.json")
	if not FileAccess.file_exists(path):
		return
	var gd: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var node := Node3D.new()
	node.name = "GroundDetail"
	_root.add_child(node)
	var gmats := []
	for k in gd.mat_ids:
		var md: Dictionary = gd.materials[k]
		var m := _tiling(str(md.tex)) as StandardMaterial3D
		m.uv1_triplanar = true; m.uv1_world_triplanar = true
		var uv := float(md.uv); m.uv1_scale = Vector3(uv, uv, uv)
		m.albedo_color = Color(str(md.tint))
		m.roughness = float(md.rough); m.metallic = float(md.metal)
		gmats.append(m)
	var t := float(gd.get("thick", 0.01))
	var cell := float(gd.get("merge_cell", 48.0))
	var groups := {}
	for it in gd.items:
		var key := "%d_%d_%d" % [int(it[0]), floori(float(it[1]) / cell), floori(float(it[2]) / cell)]
		if not groups.has(key):
			groups[key] = {"mat": gmats[int(it[0])], "items": []}
		var xf := Transform3D(Basis(Vector3.UP, deg_to_rad(float(it[6]))), Vector3(float(it[1]), float(it[5]) - t * 0.5, float(it[2])))
		groups[key].items.append([xf, Vector3(float(it[3]), t, float(it[4]))])
	var merger = load("res://art_pass/districts/alley/merge_boxes.gd")
	for key in groups:
		var out := MeshInstance3D.new()
		out.name = "Ground_" + key
		out.mesh = merger._build(groups[key].items)
		out.material_override = groups[key].mat
		out.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		out.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.add_child(out)
```
Note: `gmats` (not `mats`) because `mats` is a member of the slice builder. `merger._build` is merge_boxes' existing
static packer; if you prefer not to call an underscore function from outside, rename it `build` there (one call site, in `merge()`).
