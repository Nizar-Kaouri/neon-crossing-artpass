@tool
extends "res://art_pass/slice/slice_builder.gd"
## STEP 7 / DISTRICT 1: the OLD ALLEY dressed in the approved art-pass style (owner: Claude).
## Layout = the old lab map, exactly: every collider comes from art_pass/export/layout_dump.json, every building
## footprint / opening / roof height from ALLEY_INVENTORY.json (ChatGPT T24). This builder only ADDS visuals:
## - cladding 3 cm OUTSIDE each building's collision face, never across a doorway or a porch;
## - eaves, signs, lanterns, noren only above 2.9 m or flush on walls (nothing new in walkable space);
## - no new collision at all. In the full map the old collision + gameplay stay; only the old visuals are hidden.
## Standalone (this scene): the old collision is rebuilt from the dump so the district can be walked and baked.

## Reusable for every district (Step 7 plan, 2026-10-06): a district scene sets these in the inspector.
@export_file("*.json") var INV := "res://art_pass/districts/alley/ALLEY_INVENTORY.json"
@export_file("*.json") var HULLS := "res://art_pass/districts/alley/old_convex_hulls.json"   # tools/convex_hulls.py
@export var REGION := Rect2(20, -56, 80, 62)            # x 20..100, z -56..6 (alley + a margin)
@export var TRAD: Array[String] = ["ramen", "izakaya", "noodle_stand"]   # building kinds dressed traditional
@export var SKIP_IDS: Array[String] = ["B09"]           # buildings dressed by a neighbouring district
@export_file("*.json") var DRESS := ""                   # STREET_DRESS.json (tools/inventory/street_dress.py): props + old boxes they replace
@export var SKIP_ROLES: Array[String] = []             # mall #5: roles whose old visuals are not drawn (collision stays)
@export var SKYLINE_CENTER := Vector2(-10, 40)           # station R5: one skyline ring for the whole map, outside its walls
@export var SKYLINE_RADII := Vector2(230, 290)           # near, far ring radius (m): >= 70 m past the map corners
@export var CABLES := PackedVector3Array([Vector3(36, 6.2, -26.4), Vector3(47.5, 6.2, -26.4), Vector3(61, 6.2, -26.4), Vector3(69.5, 6.2, -26.4), Vector3(82, 6.2, -26.4)])   # overhead cable bundles (rotated 90)
const DUMP := "res://art_pass/export/layout_dump.json"
const BACKFACE_OFF := [4065]                             # T32: concave shapes that are one-sided in the old map (shrine HillSurface); all others two-sided
@export var dress := true                               # false = old collision/visuals only (route diagnostics)
@export var standalone := true                          # false inside the full map: old collision already there

var inv: Dictionary
var _crate_mat: Material = null
var _hidden := {}                                       # dump indices whose old box visual is replaced by a dressing prop
var _roles := {}                                        # dump index -> structure role (inventory "structures")
var _role_mats := {}
var _sign_i := 0
var _all_openings := []                                # T34: every opening of every building: [axis_is_z, plane, u0, u1]
var _footprints := []                                   # [id, Rect2] of every building
var _face_n := Vector3.ZERO
var _face_plane := 0.0
var _sill := 0.0
var _face_holes := []                                   # openings of the face being dressed: [u0, u1, y0, y1]


func _build() -> void:
	var old := get_node_or_null("Built")
	if old:
		remove_child(old)
		old.free()
	_root = Node3D.new()
	_root.name = "Built"
	add_child(_root)
	_count = 0
	_load_libs()
	inv = JSON.parse_string(FileAccess.get_file_as_string(INV))
	for lm in ["lantern_paper", "lantern_red"]:                   # T26: lanterns read as white bulbs
		(_mat(lm) as StandardMaterial3D).emission_energy_multiplier = 0.9
	for st in inv.get("structures", []):
		if st is Dictionary and st.has("dump_index") and st.has("role"):     # shrine-style structure list only
			_roles[int(st.dump_index)] = str(st.role)
	var dress_data: Dictionary = {}
	if DRESS != "" and FileAccess.file_exists(DRESS):
		dress_data = JSON.parse_string(FileAccess.get_file_as_string(DRESS))
		for h in dress_data.get("hide", []):
			_hidden[int(h)] = true
	if standalone:
		_old_layout()
	if not dress:
		_own(_root)
		return
	_collect_openings()
	for b in inv.buildings:
		if str(b.id) in SKIP_IDS:
			continue                                    # crossing building: dressed with the crossing district
		_dress(b)
	_street()
	_ground_patches()
	if not dress_data.is_empty():
		_street_dress(dress_data.get("props", []))
	if not _roles.is_empty():
		_structure_props()
	if inv.has("panels"):
		_panels()
	_district_extras()
	_skyline()
	var merger = load("res://art_pass/districts/alley/merge_boxes.gd")
	var hulls: int = merger.merge_hulls(_root, 48.0)
	var merged: int = merger.merge(_root, 48.0)
	var quads: int = merger.merge_quads(_root, 48.0)
	var unshadowed := _small_props_no_shadow()
	print("DISTRICT %s: merged boxes into %d meshes, quads into %d, hulls into %d, %d small props cast no shadow" % [get_parent().name, merged, quads, hulls, unshadowed])
	_own(_root)


# ------------------------------------------------------------------ the old layout, from the dump
func _old_layout() -> void:
	var dump: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DUMP))
	# T28: one StaticBody3D per ORIGINAL body (grouped by its dump path), not one body for everything, so contacts
	# and seams between shapes behave like the old map (ramps to the apartment roof / shrine approach regressed).
	var holder := Node3D.new()
	holder.name = "OldLayoutCollision"
	_root.add_child(holder)
	var bodies := {}
	var paving := _tiling("paving_stone")
	paving.uv1_triplanar = true
	paving.uv1_world_triplanar = true
	paving.uv1_scale = Vector3(0.5, 0.5, 0.5)
	paving.albedo_color = Color(0.84, 0.87, 0.97)                  # T26 #1: cooler blue-grey stone, joints readable
	paving.normal_scale = 1.6
	var concrete := _tiling("concrete_warm")
	concrete.uv1_triplanar = true
	concrete.uv1_world_triplanar = true
	concrete.uv1_scale = Vector3(0.5, 0.5, 0.5)
	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color("3e4250")
	metal.metallic = 0.4
	metal.roughness = 0.5
	var roofing := _tiling("concrete_warm")
	roofing.uv1_triplanar = true
	roofing.uv1_world_triplanar = true
	roofing.uv1_scale = Vector3(0.5, 0.5, 0.5)
	roofing.albedo_color = Color(0.62, 0.6, 0.62)                # weathered roof deck, darker than walls
	var crate := _tiling("timber_planks")
	crate.uv1_triplanar = true
	crate.uv1_world_triplanar = true
	crate.uv1_scale = Vector3(1, 1, 1)
	# T27 fix: ALL old collision is rebuilt (the route audit walks beyond the alley and many shapes have their
	# origin outside the region, e.g. ground slabs and the shrine stairs at origin 0,0,0). Visuals only for shapes
	# whose world bounds touch the region. Convex visuals use hulls precomputed from the dump (old_convex_hulls.json).
	var hulls: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(HULLS)) if FileAccess.file_exists(HULLS) else {}
	var i := 0
	var idx := -1
	for s in dump.static:
		idx += 1
		var xf := _xf(s.xf)
		var cs := CollisionShape3D.new()
		cs.transform = xf
		var mesh: Mesh
		match str(s.type):
			"box":
				var b := BoxShape3D.new(); b.size = _v3(s.size); cs.shape = b
				var bm := BoxMesh.new(); bm.size = b.size; bm.add_uv2 = true; mesh = bm
			"convex":
				var c := ConvexPolygonShape3D.new(); c.points = _pts(s.points); cs.shape = c
				mesh = _hull_mesh(c.points, hulls.get(str(idx), []))
			"concave":
				var cc := ConcavePolygonShape3D.new(); cc.set_faces(_pts(s.faces)); cc.backface_collision = bool(s.get("backface", idx not in BACKFACE_OFF)); cs.shape = cc   # T31: old stair flights collide on both sides; the dump never stored it
				var stc := SurfaceTool.new(); stc.begin(Mesh.PRIMITIVE_TRIANGLES)
				var fp := _pts(s.faces)
				for fi in range(0, fp.size(), 3):          # dump faces are counter-clockwise; Godot front faces are clockwise
					stc.add_vertex(fp[fi]); stc.add_vertex(fp[fi + 2]); stc.add_vertex(fp[fi + 1])
				stc.generate_normals(); mesh = stc.commit()
			"cylinder":
				var cy := CylinderShape3D.new(); cy.radius = s.radius; cy.height = s.height; cs.shape = cy
				var cm := CylinderMesh.new(); cm.top_radius = s.radius; cm.bottom_radius = s.radius; cm.height = s.height; mesh = cm
			_:
				continue
		cs.name = "C%d" % idx
		var key := str(s.get("path", "unnamed"))
		if not bodies.has(key):
			var sb := StaticBody3D.new()
			sb.name = "B%d" % bodies.size()
			sb.collision_layer = int(s.get("layer", 1))
			holder.add_child(sb)
			bodies[key] = sb
		(bodies[key] as StaticBody3D).add_child(cs)
		var wa: AABB = xf * _local_aabb(s, mesh) if mesh else AABB()
		if _hidden.has(idx) or str(_roles.get(idx, "")) in SKIP_ROLES:
			continue                                    # replaced by a dressing prop / drawn by another district
		if str(_roles.get(idx, "")) == "stair_flight":
			continue                                    # shown as real steps by _structure_props (collision stays the ramp)
		if mesh == null or not _touches_region(wa) or wa.size.y > 30.0:
			continue                                    # > 30 m tall = the old map's invisible boundary wall (x 92)
		var mi := MeshInstance3D.new()
		mi.name = "Old%d" % i
		i += 1
		mi.mesh = mesh
		mi.transform = xf
		var a: AABB = xf * mesh.get_aabb()
		if a.size.y < 0.6 and a.size.x * a.size.z > 4.0:
			mi.material_override = paving if a.end.y < 1.0 else roofing   # street floors vs roof decks
		elif a.size.x < 1.6 and a.size.z < 1.6 and a.size.y < 1.6 and a.position.y < 0.5:
			mi.material_override = crate                      # street cover: crates, delivery boxes
		elif a.size.x < 0.35 or a.size.z < 0.35:
			mi.material_override = metal                      # rails, posts, pipes, stair stringers
		else:
			mi.material_override = concrete
		if _roles.has(idx):                                # structure districts (shrine): material by role
			var rm := _role_mat(str(_roles[idx]))
			if rm:
				mi.material_override = rm
		if mesh is BoxMesh:
			var side := clampi(int(sqrt(a.size.x * a.size.z + 2 * a.size.y * (a.size.x + a.size.z)) * 4.0), 16, 512)
			(mesh as BoxMesh).lightmap_size_hint = Vector2i(side, side)
			mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		else:
			mi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		_root.add_child(mi)
	# gameplay props (movable): shown as their boxes, lit dynamically
	for act in dump.actors:
		var xf := _xf(act.xf)
		if not REGION.has_point(Vector2(xf.origin.x, xf.origin.z)):
			continue
		for sh in act.shapes:
			if str(sh.type) == "box":
				var mi := MeshInstance3D.new()
				var bm := BoxMesh.new(); bm.size = _v3(sh.size); mi.mesh = bm
				mi.transform = _xf(sh.xf)
				mi.material_override = metal
				_root.add_child(mi)


## T27: Low preset was 843 draw calls at camera 3 (limit 800). Small dressing (lanterns, plants, signs, menus,
## noren, pots) gets no sun shadow: each shadowed mesh costs extra draw calls per shadow cascade.
func _small_props_no_shadow() -> int:
	var n := 0
	for mi in _root.find_children("*", "GeometryInstance3D", true, false):
		var a: AABB = (mi as GeometryInstance3D).get_aabb()
		var sc: Vector3 = (mi as Node3D).global_transform.basis.get_scale()
		var sz := a.size * sc
		if maxf(sz.x, maxf(sz.y, sz.z)) < 2.5 and not str(mi.name).begins_with("Old"):
			(mi as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			n += 1
	return n


## Shrine-type districts: materials per structure role (old collision shapes shown as stone, vermilion, timber...).
func _role_mat(role: String) -> Material:
	if _role_mats.has(role):
		return _role_mats[role]
	var m: Material = null
	match role:
		"torii":
			var t := StandardMaterial3D.new(); t.albedo_color = Color("c9402f"); t.roughness = 0.55; m = t
		"stair_flight", "stair_landing", "summit_terrace", "stone_low_wall", "offering_table":
			var g := _tiling("stone_wall_blocks") as StandardMaterial3D
			g.uv1_triplanar = true; g.uv1_world_triplanar = true; g.uv1_scale = Vector3(0.5, 0.5, 0.5)
			g.albedo_color = Color(0.86, 0.84, 0.86); m = g
		"pavilion_post", "tree_trunk":
			var w := _tiling("timber_planks") as StandardMaterial3D
			w.uv1_triplanar = true; w.uv1_world_triplanar = true; w.albedo_color = Color(0.55, 0.42, 0.36); m = w
		"pavilion_roof":
			var r := _tiling("roof_kawara") as StandardMaterial3D
			r.uv1_triplanar = true; r.uv1_world_triplanar = true; r.uv1_scale = Vector3(0.5, 0.5, 0.5); m = r
		"tunnel_wall", "door_lintel", "mall_link_wall":     # underground R3: cream tiles, never the dark "thin = metal" look
			var tw := _tiling("paving_stone") as StandardMaterial3D
			tw.uv1_triplanar = true; tw.uv1_world_triplanar = true; tw.uv1_scale = Vector3(1, 1, 1)
			tw.albedo_color = Color("f1e6d2"); m = tw
		"tunnel_floor", "mall_link_floor":
			var tf := _tiling("paving_stone") as StandardMaterial3D
			tf.uv1_triplanar = true; tf.uv1_world_triplanar = true; tf.uv1_scale = Vector3(1, 1, 1)
			tf.albedo_color = Color(0.78, 0.74, 0.72); m = tf
		"hill_surface":
			var h := _tiling("plaster_cream") as StandardMaterial3D        # moss + grass: green tint over a soft texture
			h.uv1_triplanar = true; h.uv1_world_triplanar = true; h.uv1_scale = Vector3(0.25, 0.25, 0.25)
			h.albedo_color = Color(0.5, 0.62, 0.42); h.roughness = 1.0; m = h
	_role_mats[role] = m
	return m


## Shrine-type districts: real steps over each ramp collider, stone cheek walls beside them (outside the walkable
## width), and the props listed in the inventory (lanterns grounded on the hill / landings by the extraction tool).
func _structure_props() -> void:
	var node := Node3D.new()
	node.name = "StructureProps"
	_root.add_child(node)
	var stone := _role_mat("stair_flight")
	for st in inv.get("structures", []):
		if not (st is Dictionary and str(st.get("role", "")) == "stair_flight" and st.has("axis")):
			continue
		var ax: Dictionary = st.axis
		var o := Vector3(ax.origin_xz[0], 0, ax.origin_xz[1])
		var dv := Vector3(ax.dir_xz[0], 0, ax.dir_xz[1]).normalized()
		var pv := Vector3(-dv.z, 0, dv.x)
		var a0: float = ax.along_min
		var a1: float = ax.along_max
		var y0: float = ax.y_low
		var y1: float = ax.y_high
		var wdt: float = st.width_true
		var n := maxi(1, ceili((y1 - y0) / 0.12))           # T34: 12 cm risers so treads can stay under the walking surface
		var run := (a1 - a0) / n
		var rise := (y1 - y0) / n
		var basis := Basis(pv, Vector3.UP, -dv)            # local x = across, local -z = uphill
		for k in n:
			var top := y0 + k * rise + 0.04                 # T34: tread top <= ramp + 4 cm (safety gate); feet at most ~8 cm above a tread
			var bottom := y0 - 0.3
			var c := o + dv * (a0 + (k + 0.5) * run) + pv * float(ax.mid_across)
			if _step_hits_landing(c, dv * run * 0.5, pv * wdt * 0.5, top):
				continue                                    # T35: the landing slab is the surface here; a step would stick out of it
			var b := MeshInstance3D.new()
			var bm := BoxMesh.new(); bm.size = Vector3(wdt, top - bottom, run + 0.01); bm.add_uv2 = true
			b.mesh = bm; b.material_override = stone; b.gi_mode = GeometryInstance3D.GI_MODE_STATIC
			b.transform = Transform3D(basis, Vector3(c.x, (top + bottom) * 0.5, c.z))
			node.add_child(b)
			for side in [-1.0, 1.0]:                        # cheek walls just outside the stair width
				var cw0: Vector3 = c + pv * float(side) * (wdt * 0.5 + 0.15)
				if _on_landing(cw0, top + 0.3):
					continue                                # T34: never stick up into a landing's walkable area
				var w := MeshInstance3D.new()
				var wm := BoxMesh.new(); wm.size = Vector3(0.3, top + 0.3 - bottom, run + 0.01); wm.add_uv2 = true
				w.mesh = wm; w.material_override = stone; w.gi_mode = GeometryInstance3D.GI_MODE_STATIC
				var cw: Vector3 = c + pv * float(side) * (wdt * 0.5 + 0.15)
				w.transform = Transform3D(basis, Vector3(cw.x, (top + 0.3 + bottom) * 0.5, cw.z))
				node.add_child(w)
	for p in inv.get("props", []):
		place(node, str(p.piece), Vector3(p.pos[0], p.pos[1], p.pos[2]), float(p.rot))


## Street dressing: one MultiMesh per piece type (one draw call each), lit by probes, no collision.
func _street_dress(props: Array) -> void:
	var by_piece := {}
	for p in props:
		var k := str(p.piece)
		if not by_piece.has(k):
			by_piece[k] = []
		by_piece[k].append(p)
	var holder := Node3D.new()
	holder.name = "StreetDress"
	_root.add_child(holder)
	for k in by_piece:
		var src: MeshInstance3D = lib.get(k)
		if src == null:
			push_warning("street dress: missing piece " + k)
			continue
		var mesh := src.mesh.duplicate() as Mesh
		for s in mesh.get_surface_count():
			var m := mesh.surface_get_material(s)
			var mn: String = m.resource_name if m else ""
			if k == "P_crates_stack":                       # kit crates carry lantern/noren materials: use plain timber
				if _crate_mat == null:
					_crate_mat = _tiling("timber_planks")
					(_crate_mat as StandardMaterial3D).uv1_triplanar = true
					(_crate_mat as StandardMaterial3D).albedo_color = Color(0.72, 0.6, 0.5)
				mesh.surface_set_material(s, _crate_mat)
			elif not mn.ends_with("_mat"):
				mesh.surface_set_material(s, _mat(mn, k))
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = by_piece[k].size()
		var i := 0
		for p in by_piece[k]:
			var sc: Array = p.get("scale", [1, 1, 1])
			var bas := Basis(Vector3.UP, deg_to_rad(float(p.rot))).scaled_local(Vector3(sc[0], sc[1], sc[2]))
			mm.set_instance_transform(i, Transform3D(bas, Vector3(p.pos[0], p.pos[1], p.pos[2])))
			i += 1
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Dress_" + k
		mmi.multimesh = mm
		mmi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		if k in ["G_drain_grate", "P_cable_bundle_6m", "P_ac_unit"]:      # T36: small wall/ground pieces cast no sun shadow
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		holder.add_child(mmi)


func _step_hits_landing(c: Vector3, half_along: Vector3, half_across: Vector3, top: float) -> bool:
	for su in [-1.0, -0.5, 0.0, 0.5, 1.0]:
		for sv in [-1.0, -0.5, 0.0, 0.5, 1.0]:
			var p: Vector3 = c + half_along * float(su) + half_across * float(sv)
			for st in inv.get("structures", []):
				if st is Dictionary and str(st.get("role", "")) in ["stair_landing", "summit_terrace"]:
					var lo := _v3(st.aabb_min)
					var hi := _v3(st.aabb_max)
					if p.x > lo.x - 0.05 and p.x < hi.x + 0.05 and p.z > lo.z - 0.05 and p.z < hi.z + 0.05 and top > hi.y:
						return true
	return false


func _over_landing(p: Vector3, r: float) -> bool:
	for st in inv.get("structures", []):
		if st is Dictionary and str(st.get("role", "")) in ["stair_landing", "summit_terrace"]:
			var lo := _v3(st.aabb_min)
			var hi := _v3(st.aabb_max)
			if p.x > lo.x - r and p.x < hi.x + r and p.z > lo.z - r and p.z < hi.z + r:
				return true
	return false


## Homes/park R2: flat ground skins from the inventory (lawns, paved paths), top <= 1.2 cm above the old ground.
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


## Districts that need their own dressing override this (runs after structures/panels, before merging). mall #1
func _district_extras() -> void:
	pass


## Station/underground R1: thin visual boxes listed by the district (tiles 5 cm off walls, ceiling panels, guide lines).
var _panel_mats := {}
func _panels() -> void:
	var node := Node3D.new()
	node.name = "Panels"
	_root.add_child(node)
	for p in inv.panels:
		var key := "%s|%s|%s" % [p.mat, str(p.get("tint", "")), str(p.get("uv", 0.5))]
		if not _panel_mats.has(key):
			var m := _tiling(str(p.mat)) as StandardMaterial3D
			m.uv1_triplanar = true; m.uv1_world_triplanar = true
			var uv := float(p.get("uv", 0.5)); m.uv1_scale = Vector3(uv, uv, uv)
			if p.has("tint"):
				m.albedo_color = Color(str(p.tint))
			_panel_mats[key] = m
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new(); bm.size = Vector3(p.s[0], p.s[1], p.s[2]); bm.add_uv2 = true
		mi.mesh = bm
		mi.material_override = _panel_mats[key]
		mi.position = Vector3(p.c[0], p.c[1], p.c[2])
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		node.add_child(mi)


## Station R5: one skyline ring around the whole map (outside its boundary walls), 9 cards per layer, all directions.
func _skyline() -> void:
	for layer in [["far", SKYLINE_RADII.y, 95.0, Color(0.7, 0.62, 0.74)], ["", SKYLINE_RADII.x, 85.0, Color(0.52, 0.46, 0.58)]]:
		var tex: String = ART + ("skyline/skyline_cards_far.png" if layer[0] == "far" else "skyline/skyline_cards.png")
		var m := StandardMaterial3D.new()
		m.albedo_texture = load(tex)
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		m.alpha_scissor_threshold = 0.5
		m.albedo_color = layer[3]
		m.disable_fog = true
		var r: float = layer[1]
		for k in 9:
			var ang := deg_to_rad(40.0 * k + (20.0 if layer[0] == "far" else 0.0))
			var q := QuadMesh.new()
			q.size = Vector2(2.0 * r * tan(deg_to_rad(21.0)), layer[2])     # cards just overlap around the ring
			var mi := MeshInstance3D.new()
			mi.name = "Skyline_%s_%d" % [layer[0], k]
			mi.mesh = q
			mi.material_override = m
			mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.position = Vector3(SKYLINE_CENTER.x + sin(ang) * r, float(layer[2]) * 0.5 - 8.0, SKYLINE_CENTER.y - cos(ang) * r)
			mi.rotation.y = -ang
			_root.add_child(mi)


func _on_landing(p: Vector3, top: float) -> bool:
	for st in inv.get("structures", []):
		if st is Dictionary and str(st.get("role", "")) in ["stair_landing", "summit_terrace"]:
			var lo := _v3(st.aabb_min)
			var hi := _v3(st.aabb_max)
			if p.x > lo.x - 0.3 and p.x < hi.x + 0.3 and p.z > lo.z - 0.3 and p.z < hi.z + 0.3 and top > hi.y:
				return true
	return false


func _local_aabb(s: Dictionary, mesh: Mesh) -> AABB:
	if str(s.type) == "convex":
		var pts := _pts(s.points)
		var a := AABB(pts[0], Vector3.ZERO)
		for q in pts:
			a = a.expand(q)
		return a
	return mesh.get_aabb()


func _touches_region(a: AABB) -> bool:
	return a.end.x >= REGION.position.x and a.position.x <= REGION.end.x and a.end.z >= REGION.position.y and a.position.z <= REGION.end.y


## Solid mesh for a convex collider (triangles from old_convex_hulls.json); null when the shape is outside the region.
func _hull_mesh(pts: PackedVector3Array, tris: Array) -> Mesh:
	if tris.is_empty():
		return null
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for t in range(0, tris.size(), 3):
		for k in [0, 2, 1]:                       # hull is counter-clockwise outward; Godot front faces are clockwise
			st.add_vertex(pts[int(tris[t + k])])
	st.generate_normals()
	return st.commit()


# ------------------------------------------------------------------ buildings
## One building: cladding on all 4 faces, windows, eaves, cornice, signs, noren, lanterns.
func _dress(b: Dictionary) -> void:
	var f: Dictionary = b.footprint
	var cx: float = f.centre_xz[0]
	var cz: float = f.centre_xz[1]
	var w: float = f.width_m
	var d: float = f.depth_m
	var H: float = float(b.roof.roof_y)
	var trad: bool = str(b.kind) in TRAD
	var node := Node3D.new()
	node.name = str(b.id) + "_" + str(b.kind)
	_root.add_child(node)
	# faces: [normal, plane coord, along-axis min, max]
	var faces := [[Vector3(0, 0, 1), cz + d * 0.5, cx - w * 0.5, cx + w * 0.5], [Vector3(0, 0, -1), cz - d * 0.5, cx - w * 0.5, cx + w * 0.5],
		[Vector3(1, 0, 0), cx + w * 0.5, cz - d * 0.5, cz + d * 0.5], [Vector3(-1, 0, 0), cx - w * 0.5, cz - d * 0.5, cz + d * 0.5]]
	for fc in faces:
		var n: Vector3 = fc[0]
		var plane: float = fc[1]
		if _inside_other(str(b.id), n, plane, (float(fc[2]) + float(fc[3])) * 0.5):
			continue                                    # T34: this face lies inside a neighbouring building (overlapping footprints)
		_face_n = n
		_face_plane = plane
		var holes := []                      # [u0, u1, y0, y1] in face coords (u = along x or z)
		var fronts := []
		var porch := false
		var street := false
		for s in b.street_facing_sides:
			var sn := Vector3(s.normal_xz[0], 0, s.normal_xz[1])
			if sn.dot(n) < 0.9:
				continue
			street = true
			for o in s.openings:
				var c := Vector3(o.centre_xyz[0], o.centre_xyz[1], o.centre_xyz[2])
				var u := c.x if absf(n.z) > 0.5 else c.z
				var setback := absf((c.z if absf(n.z) > 0.5 else c.x) - plane)
				var top: float = float(o.sill_y) + float(o.height_m) if o.has("sill_y") else c.y + float(o.height_m) * 0.5
				# "backing" openings sit 1.3 m behind the facade: the old shell has a doorway gap in the front wall
				# at the same u, so the hole goes through the facade there too (never across the whole band).
				holes.append([u - float(o.width_m) * 0.5 - 0.05, u + float(o.width_m) * 0.5 + 0.05, -1.0, top + 0.05])
				fronts.append([u, float(o.width_m), top, float(o.get("sill_y", 0.0))])
		# T34: a neighbour's doorway on (almost) the same wall line also cuts this cladding
		var z_ax := absf(n.z) > 0.5
		for og in _all_openings:
			if bool(og[0]) == z_ax and absf(float(og[1]) - plane) < 0.6 and float(og[3]) > float(fc[2]) and float(og[2]) < float(fc[3]):
				holes.append([float(og[2]) - 0.05, float(og[3]) + 0.05, -1.0, 2.6])
		# T33: decorate only after ALL openings of this face are known, so nothing lands in a neighbouring doorway
		_face_holes = holes
		for fr in fronts:
			_sill = fr[3]
			_frontage(node, n, plane, fr[0], fr[1], fr[2], trad, street, porch, str(b.kind))
		var ground_mat := "timber_planks" if trad else "concrete_warm"
		var upper_mat := "plaster_cream" if trad else "concrete_warm"
		var band := minf(3.1, H)
		_clad(node, n, plane, fc[2], fc[3], 0.0, band, holes, ground_mat)
		if H > band:
			_clad(node, n, plane, fc[2], fc[3], band, H - 0.45, holes, upper_mat)
		_cornice(node, n, plane, fc[2], fc[3], H, trad, float(b.get("cornice_depth", 0.28)))     # homes R3: shallow next to flights
		if porch:
			for u in [fc[2] + 0.12, fc[3] - 0.12]:
				_face_box(node, n, plane, u, 0.0, 0.24, band, 0.24, "timber_planks", -0.12)     # porch posts, inside the line
		# upper floors: windows on every face that sees a lane (all four here: the alley has lanes all round)
		var plain := false                                     # homes R4: no windows on "plain_faces" (flights 0.1 m off the wall)
		for pf in b.get("plain_faces", []):
			if Vector3(float(pf[0]), 0, float(pf[1])).dot(n) > 0.9:
				plain = true
		var lv := 1
		while lv * 3.1 + 2.6 < H and not plain:
			var y := lv * 3.1 + 0.9
			var span: float = fc[3] - fc[2]
			var count := maxi(1, int((span - 0.8) / 2.6))
			var pitch := span / count
			for k in count:
				_window(node, n, plane, fc[2] + pitch * (k + 0.5), y, minf(1.7, pitch - 0.7), 1.5, trad, str(b.id) + str(lv) + str(k), false, str(b.kind) in ["arcade", "pachinko", "office_tower"])
			if trad:
				_face_box(node, n, plane, (fc[2] + fc[3]) * 0.5, lv * 3.1 - 0.08, span + 0.1, 0.16, 0.10, "timber_planks", 0.11)
				if street:
					_eave(node, n, plane, fc[2], fc[3], lv * 3.1 + 0.05)
			lv += 1
		if trad and street:
			_eave(node, n, plane, fc[2], fc[3], minf(3.3, H - 0.2))
		if street and (trad or str(b.kind) == "apartment") and H > 5.0:     # T26 #3: greenery on the facades
			for k in 2:
				var uu: float = lerpf(fc[2], fc[3], 0.2 + 0.6 * k)
				var iv := _put(node, "F_ivy_wall", _face_pt(n, plane, uu, H - 0.5, 0.2), n, 3 + (k + _sign_i) % 3)
				if iv:
					iv.scale = Vector3(1.2, 1.6, 1.0)
		if trad:
			for u in [fc[2] + 0.1, fc[3] - 0.1]:
				_face_box(node, n, plane, u, 0.0, 0.2, H - 0.45, 0.14, "timber_planks", 0.1)
	# roof dressing that never sits on the walkable roof: a tank against the cornice on tall roofs only
	if H > 8.0 and not bool(b.get("roof_is_route", false)):     # homes R1: roofs that are routes stay clear
		place(node, "P_roof_antenna", Vector3(cx + w * 0.5 - 0.4, H, cz - d * 0.5 + 0.4))


## True if [u - half, u + half] keeps 10 cm away from every opening of the current face.
func _free(u: float, half: float) -> bool:
	for h in _face_holes:
		if u + half > float(h[0]) - 0.1 and u - half < float(h[1]) + 0.1:
			return false
	var z_axis := absf(_face_n.z) > 0.5
	for o in _all_openings:                             # T34: openings of neighbouring buildings facing the same way, close by
		if bool(o[0]) == z_axis and absf(float(o[1]) - _face_plane) < 2.0 and u + half > float(o[2]) - 0.1 and u - half < float(o[3]) + 0.1:
			return false
	return true


func _collect_openings() -> void:
	_all_openings.clear()
	_footprints.clear()
	for b in inv.buildings:
		var f: Dictionary = b.footprint
		_footprints.append([str(b.id), Rect2(float(f.centre_xz[0]) - float(f.width_m) * 0.5, float(f.centre_xz[1]) - float(f.depth_m) * 0.5, float(f.width_m), float(f.depth_m))])
		for sd in b.get("street_facing_sides", []):
			var z_axis := absf(float(sd.normal_xz[1])) > 0.5
			for o in sd.openings:
				var u: float = float(o.centre_xyz[0]) if z_axis else float(o.centre_xyz[2])
				var pl: float = float(o.centre_xyz[2]) if z_axis else float(o.centre_xyz[0])
				_all_openings.append([z_axis, pl, u - float(o.width_m) * 0.5, u + float(o.width_m) * 0.5])


func _inside_other(id: String, n: Vector3, plane: float, u_mid: float) -> bool:
	var p := Vector2(plane, u_mid) if absf(n.x) > 0.5 else Vector2(u_mid, plane)
	for fp in _footprints:
		if fp[0] != id and (fp[1] as Rect2).grow(-0.2).has_point(p):
			return true
	return false


## Shopfront dressing around one street opening.
func _frontage(node: Node3D, n: Vector3, plane: float, u: float, ow: float, top: float, trad: bool, street: bool, porch: bool, kind: String) -> void:
	var y_sign := maxf(top + 0.4, 3.2)
	if trad:
		# noren: kept above 2.02 m so the doorway stays visually clear (T26 safety table)
		var noren := "A_noren_2_4m" if ow >= 2.4 else "A_noren_1_8m"
		var nw := 2.4 if ow >= 2.4 else 1.8
		var nh := 1.2 if ow >= 2.4 else 0.9
		var sy := (top - 0.02 - maxf(2.25, _sill + 2.1)) / nh   # T34: >= 2.1 m above this opening's own sill
		if sy >= 0.25:
			var nm := _put(node, noren, _face_pt(n, plane, u + nw * 0.5 if n.z > 0.5 or n.x < -0.5 else u - nw * 0.5, top - 0.02, 0.06), n, _sign_i % 4)
			if nm:
				nm.scale.y = minf(1.0, sy)
		for side in [-1.0, 1.0]:
			if not _free(u + side * (ow * 0.5 + 0.55), 0.25):
				continue
			var lp := _face_pt(n, plane, u + side * (ow * 0.5 + 0.55), top - 0.05, 0.45)
			_put(node, "P_lantern_red" if kind == "izakaya" else "P_lantern_paper", lp, n)
			_light("Lantern_%d" % _count, lp + n * 0.2 - Vector3(0, 0.4, 0), Color("ffa04a"), 1.5, 5.0, node)
		_put(node, "A_sign_vertical", _face_pt(n, plane, u - ow * 0.5 - 0.9, y_sign, 0.02), n, _sign_i % 8)
		if _free(u + ow * 0.5 + 0.55, 0.35):
			_put(node, "P_menu_board", _face_pt(n, plane, u + ow * 0.5 + 0.55, 0.0, 0.25), n, _sign_i % 4)
	else:
		match kind:
			"arcade":                                                    # big lit screen over the entrance
				var q := QuadMesh.new(); q.size = Vector2(4.2, 3.0)
				var scr := MeshInstance3D.new(); scr.mesh = q; scr.material_override = _screen()
				scr.position = _face_pt(n, plane, u, top + 2.4, 0.14); scr.rotation.y = atan2(n.x, n.z)
				scr.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
				node.add_child(scr)
				_light("Screen_%d" % _count, _face_pt(n, plane, u, top + 2.0, 2.0), Color("c070ff"), 1.6, 8.0, node)
			"pachinko", "konbini":                                       # wide light-box band over the entrance
				var lb := _put(node, "M_sign_lightbox_2m", _face_pt(n, plane, u + (1.0 if n.z > 0.5 or n.x < -0.5 else -1.0) * 1.0 * 3.0, top + 0.35, 0.02), n, 5 if kind == "pachinko" else 2)
				if lb:
					lb.scale = Vector3(3.0, 1.6 if kind == "pachinko" else 1.0, 1.0)
			_:
				_put(node, "M_sign_lightbox_2m", _face_pt(n, plane, u + 1.0, y_sign, 0.02), n, (_sign_i + 3) % 8)
		if not porch:                                              # shop windows either side of the door, flush on the wall
			for side in [-1.0, 1.0]:
				if _free(u + side * (ow * 0.5 + 1.25), 1.1):
					_window(node, n, plane, u + side * (ow * 0.5 + 1.25), 0.5, 1.9, 2.0, false, "Shop%d%d" % [_count, int(side)], true)
		_light("Shop_%d" % _count, _face_pt(n, plane, u, top - 0.4, 1.2), Color("ffd2a0"), 1.5, 6.0, node)
	_light("Spill_%d" % _count, _face_pt(n, plane, u, 1.2, -1.5 if porch else -0.8), Color("ffb060"), 1.4, 5.5, node)
	# plants either side of the door, flush against the wall (small, decorative, no collision)
	for side in [-1.0, 1.0]:
		if not _free(u + side * (ow * 0.5 + 1.0), 0.4):
			continue
		var pp := _face_pt(n, plane, u + side * (ow * 0.5 + 1.0), 0.0, 0.35)
		place(node, "P_pot_round", pp)
		place(node, "F_pot_plant", pp, 0, 10 + (_sign_i + int(side)) % 6)
	_sign_i += 1


# ------------------------------------------------------------------ face helpers (u along the face, y up, out = distance outside)
func _face_pt(n: Vector3, plane: float, u: float, y: float, out: float) -> Vector3:
	if absf(n.z) > 0.5:
		return Vector3(u, y, plane + n.z * out)
	return Vector3(plane + n.x * out, y, u)


## Put a kit piece so its front faces `n` (kit fronts face +Z; origin = bottom-left of the outer face).
func _put(node: Node3D, piece: String, p: Vector3, n: Vector3, cell := -1) -> MeshInstance3D:
	var rot := rad_to_deg(atan2(n.x, n.z))
	return place(node, piece, p, rot, cell)


func _face_box(node: Node3D, n: Vector3, plane: float, u: float, y0: float, du: float, dy: float, thick: float, m: String, out := 0.03) -> void:
	var c := _face_pt(n, plane, u, y0 + dy * 0.5, out + thick * 0.5 * (1.0 if out >= 0 else -1.0))
	var size := Vector3(du, dy, thick) if absf(n.z) > 0.5 else Vector3(thick, dy, du)
	block("F%d" % _count, c, size, m, node)
	_count += 1


## Wall cladding over [u0,u1] x [y0,y1], leaving holes open.
func _clad(node: Node3D, n: Vector3, plane: float, u0: float, u1: float, y0: float, y1: float, holes: Array, m: String) -> void:
	var rects := [[u0, u1, y0, y1]]
	for h in holes:
		var next := []
		for r in rects:
			var a0 := maxf(r[0], h[0]); var a1 := minf(r[1], h[1]); var b0 := maxf(r[2], h[2]); var b1 := minf(r[3], h[3])
			if a0 >= a1 or b0 >= b1:
				next.append(r)
				continue
			if r[2] < b0: next.append([r[0], r[1], r[2], b0])
			if b1 < r[3]: next.append([r[0], r[1], b1, r[3]])
			if r[0] < a0: next.append([r[0], a0, b0, b1])
			if a1 < r[1]: next.append([a1, r[1], b0, b1])
		rects = next
	for r in rects:
		if r[1] - r[0] > 0.05 and r[3] - r[2] > 0.05:
			_face_box(node, n, plane, (r[0] + r[1]) * 0.5, r[2], r[1] - r[0], r[3] - r[2], 0.06, m, 0.05)   # clears the old 6 cm display bays


func _cornice(node: Node3D, n: Vector3, plane: float, u0: float, u1: float, H: float, trad: bool, depth := 0.28) -> void:
	var ext := 0.25 if depth >= 0.28 else depth              # homes R3: a shallow cornice also overhangs the corners less
	_face_box(node, n, plane, (u0 + u1) * 0.5, H - 0.45, u1 - u0 + 2.0 * ext, 0.42, depth, "roof_kawara" if trad else "metal_panel", 0.0)


## Lean-to tiled eave along a face at height y (projects 1.1 m, always above head height).
func _eave(node: Node3D, n: Vector3, plane: float, u0: float, u1: float, y: float) -> void:
	if y < 2.9:
		return
	var u := u0
	while u < u1 - 0.5:
		var seg := 4.0 if u1 - u >= 4.0 else 2.0
		var p := _face_pt(n, plane, u if n.z > 0.5 or n.x < -0.5 else u + seg, y, 0.03)
		_put(node, "A_canopy_roof_%dm" % int(seg), p, n)
		u += seg


var _tone_mat: ShaderMaterial
func _window(node: Node3D, n: Vector3, plane: float, u: float, y: float, ww: float, wh: float, trad: bool, key: String, shop := false, tone := false) -> void:
	var q := QuadMesh.new()
	q.size = Vector2(ww, wh)
	var mi := MeshInstance3D.new()
	mi.name = "Win" + key
	mi.mesh = q
	mi.material_override = _mat("window_interior" if trad else "window_room", "A_lattice" if trad else ("A_shopfront_4m" if shop else "M_window_bay_2m"))
	if tone:                                   # offices / arcade / pachinko upstairs: darker, cooler glazing (T26)
		if _tone_mat == null:
			_tone_mat = (_mat("window_room", "M_window_bay_2m") as ShaderMaterial).duplicate()
			_tone_mat.set_shader_parameter("brightness", 0.6)
			_tone_mat.set_shader_parameter("lit_chance", 0.55)
			_tone_mat.set_shader_parameter("wall_col", Color(0.55, 0.6, 0.7))
		mi.material_override = _tone_mat
	mi.position = _face_pt(n, plane, u, y + wh * 0.5, 0.115)
	mi.rotation.y = atan2(n.x, n.z)
	mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	node.add_child(mi)
	var fm := "timber_planks" if trad else "metal_panel"
	_face_box(node, n, plane, u, y - 0.08, ww + 0.2, 0.08, 0.09, fm, 0.1)
	_face_box(node, n, plane, u, y + wh, ww + 0.2, 0.08, 0.09, fm, 0.1)
	for s in [-1.0, 1.0]:
		_face_box(node, n, plane, u + s * (ww * 0.5 + 0.05), y, 0.08, wh, 0.09, fm, 0.1)
	if trad:
		var bars := int(ww / 0.12)
		for k in range(1, bars):
			_face_box(node, n, plane, u - ww * 0.5 + k * ww / bars, y, 0.035, wh, 0.04, fm, 0.13)


# ------------------------------------------------------------------ street
func _street() -> void:
	# overhead cables across the main lane and lamps along it, all above head height
	for c in CABLES:
		place(_root, "P_cable_bundle_6m", c, 90)
	for l in inv.get("district_lights", []):              # station/underground R2: baked lamps at any height
		_light("DLamp_%d" % _count, Vector3(l.p[0], l.p[1], l.p[2]), Color(str(l.col)), float(l.e), float(l.r))
		_count += 1
	for l in inv.get("lights_in_or_affecting_region", []):
		var p := Vector3(l.position[0], l.position[1], l.position[2])
		if p.y > 0.5 and p.y < 7.0 and REGION.has_point(Vector2(p.x, p.z)):
			_light("OldLamp_%d" % _count, p, Color("ffc890"), 1.4, 7.0)
			_count += 1


# ------------------------------------------------------------------ helpers
static func _xf(a: Array) -> Transform3D:
	return Transform3D(Basis(Vector3(a[0], a[1], a[2]), Vector3(a[3], a[4], a[5]), Vector3(a[6], a[7], a[8])), Vector3(a[9], a[10], a[11]))


static func _v3(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


static func _pts(a: Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	for i in range(0, a.size(), 3):
		out.append(Vector3(a[i], a[i + 1], a[i + 2]))
	return out
