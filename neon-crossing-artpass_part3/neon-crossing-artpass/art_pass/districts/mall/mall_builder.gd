@tool
extends "res://art_pass/districts/alley/alley_builder.gd"
## DISTRICT: the oval MALL (Claude, cloud). A thin subclass of the shared district builder: the shared builder still
## rebuilds the old collision from the dump and draws every collider; this file only adds what the mall needs.
## Everything here is visual. No collision is added, moved or resized. See BUILDER_REQUESTS.md: once Claude (main)
## merges these hooks into alley_builder.gd, mall.tscn can point at the shared builder and this file goes away.
## - role materials for the mall roles in MALL_INVENTORY.json (shop fronts and facade glass use the slice's
##   mall_glass shader, so the shops are the slice's painted strip behind curved glass);
## - the ~3 200 convex colliders are merged into one mesh per (material, 48 m cell) instead of one mesh each;
## - shop signs (one mesh, one atlas material), two portrait screens on the outer wall, baked lights.
## Sign and screen positions come from districts/mall/tools/mall_inventory.py and are checked by self_check.py.

const MALL_CELL := 48.0
var _mall_mats := {}


## Called by the shared _build() just before the box merger runs: add the mall dressing there.
func _skyline() -> void:
	var dress_info: Dictionary = inv.get("dressing", {})
	var m: Dictionary = inv.get("mall", {})
	if m.has("centre_xz"):
		_mall_center = Vector3(m.centre_xz[0], 0.0, m.centre_xz[1])
	_mall_signs(dress_info.get("signs", []))
	_mall_screens(dress_info.get("screens", []))
	_mall_trims(dress_info.get("trims", []))
	for l in dress_info.get("lights", []):
		_light("MallLight_%d" % _count, Vector3(l.pos[0], l.pos[1], l.pos[2]), Color(str(l.color)), float(l.energy), float(l.range))
		_count += 1
	var hulls := _merge_hulls()
	print("DISTRICT mall: merged %d convex collider visuals into %d meshes" % [hulls.x, hulls.y])
	super()


# ------------------------------------------------------------------ materials per role
func _tri(n: String, col: Color, scale := 0.5) -> StandardMaterial3D:
	var t := _tiling(n) as StandardMaterial3D
	t.uv1_triplanar = true
	t.uv1_world_triplanar = true
	t.uv1_scale = Vector3(scale, scale, scale)
	t.albedo_color = col
	return t


func _flat(col: Color, metallic := 0.0, rough := 0.6) -> StandardMaterial3D:
	var s := StandardMaterial3D.new()
	s.albedo_color = col
	s.metallic = metallic
	s.roughness = rough
	return s


## The slice's curved mall glass (painted shops behind glass), mapped around the oval's centre.
## y0 / storey / step: where one row of glass starts, how tall it is, and the floor-to-floor step.
func _glass(key: String, y0: float, storey: float, radius: float) -> ShaderMaterial:
	if _mall_mats.has(key):
		return _mall_mats[key]
	var sm := ShaderMaterial.new()
	sm.shader = load(ART + "shaders/mall_glass.gdshader")
	sm.set_shader_parameter("strip", load(ART + "textures/tiling/mall_interior.png"))
	sm.set_shader_parameter("center", Vector3(_mall_center.x, y0, _mall_center.z))
	sm.set_shader_parameter("radius", radius)
	sm.set_shader_parameter("storey", storey)
	sm.set_shader_parameter("floor_step", 5.5)
	_mall_mats[key] = sm
	return sm


func _role_mat(role: String) -> Material:
	if _role_mats.has(role):
		return _role_mats[role]
	var m: Material = null
	match role:
		"floor_slab":                                            # polished warm stone promenades
			m = _tri("paving_stone", Color(1.0, 0.95, 0.88), 0.4)
		"plaza", "ground":
			m = _tri("paving_stone", Color(0.84, 0.87, 0.97), 0.5)  # same cool street stone as the other districts
		"outer_wall", "shop_ceiling":                            # the slice's cream mall shell and floor bands
			m = _tri("plaster_cream", Color(1, 1, 1), 0.5)
		"roof":                                                  # cool grey deck: the warm texture alone read terracotta
			m = _tri("concrete_warm", Color(0.56, 0.57, 0.66), 0.5)
		"atrium_curb", "atrium_rail", "facade_sill":             # climbable edges: the light trim (STYLE readability)
			m = _flat(Color("e8e2da"), 0.2, 0.45)
		"mullion", "column", "escalator_handrail", "roof_bridge", "mast", "misc":
			m = _flat(Color("3e4250"), 0.4, 0.5)
		"entrance_canopy":                                       # the two north entrance portals: cream shell
			m = _tri("plaster_cream", Color(0.92, 0.9, 0.88), 0.5)
		"atrium_platform":                                       # parkour platforms in the void: light, readable
			m = _tri("concrete_warm", Color(1.0, 0.97, 0.92), 0.5)
		"escalator":
			m = _tri("metal_panel", Color(0.55, 0.57, 0.64), 1.0)
		"escalator_balustrade":
			var g := _flat(Color(0.62, 0.7, 0.8, 0.35), 0.4, 0.08)
			g.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m = g
		"promenade_furniture", "shop_fixture", "cafe_fixture":
			m = _tri("timber_planks", Color(0.75, 0.6, 0.5), 1.0)
		"underground", "basement_wall":
			m = _tri("concrete_warm", Color(0.7, 0.68, 0.7), 0.5)
		"shop_front":                                            # one 3.84 m storey of shops per floor
			m = _glass("front", 0.0, 3.84, 30.0)
		"facade_glass":                                          # outer glass rows, 2.52 m tall from +0.8
			m = _glass("facade", 0.8, 2.52, 40.0)
	if m == null:
		return super._role_mat(role)
	_role_mats[role] = m
	return m


# ------------------------------------------------------------------ draw calls
## The shared builder draws each convex collider as its own MeshInstance3D ("Old<n>", ArrayMesh, probe-lit).
## The mall has ~3 200 of them: merge them per (material, 48 m cell). Normals are rebuilt FLAT per triangle: the
## hulls' smoothed normals shade each of the 128 ring segments as a gradient (fluted roof / walls).
## Returns (meshes in, meshes out).
func _merge_hulls() -> Vector2i:
	var groups := {}
	var n_in := 0
	for mi in _root.get_children():
		if not (mi is MeshInstance3D) or not str(mi.name).begins_with("Old"):
			continue
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if not (mesh is ArrayMesh) or mi.material_override == null:
			continue
		var t: Transform3D = (mi as MeshInstance3D).transform
		var key := "%d|%d|%d" % [mi.material_override.get_instance_id(), floori(t.origin.x / MALL_CELL), floori(t.origin.z / MALL_CELL)]
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
				fn = -fn                                        # keep the side the hull mesh says is outside
			pos.append_array([a, b, c])
			nor.append_array([fn, fn, fn])
		groups[key].pos = pos
		groups[key].nor = nor
		_root.remove_child(mi)
		mi.queue_free()
		n_in += 1
	var made := 0
	for key in groups:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = groups[key].pos
		arrays[Mesh.ARRAY_NORMAL] = groups[key].nor
		var am := ArrayMesh.new()
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var out := MeshInstance3D.new()
		out.name = "MallHulls_%d" % made
		out.mesh = am
		out.material_override = groups[key].mat
		out.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC        # no lightmap UV2 yet (BUILDER_REQUESTS #2)
		_root.add_child(out)
		made += 1
	return Vector2i(n_in, made)


# ------------------------------------------------------------------ dressing
## All shop signs in ONE mesh: each quad's UVs point at its own cell of the sign atlas (2 x 4 cells).
func _mall_signs(signs: Array) -> void:
	if signs.is_empty():
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for s in signs:
		var c := Vector3(s.pos[0], s.pos[1], s.pos[2])
		var n := Vector3(s.normal[0], 0, s.normal[2]).normalized()
		var tg := Vector3(n.z, 0, -n.x)                          # left -> right seen from the front
		var hw: float = float(s.size[0]) * 0.5
		var hh: float = float(s.size[1]) * 0.5
		var cell := int(s.cell)
		var u0 := float(cell % 2) / 2.0
		var v0 := float(cell / 2) / 4.0
		var p := [c - tg * hw - Vector3.UP * hh, c + tg * hw - Vector3.UP * hh, c + tg * hw + Vector3.UP * hh, c - tg * hw + Vector3.UP * hh]
		var uv := [Vector2(u0, v0 + 0.25), Vector2(u0 + 0.5, v0 + 0.25), Vector2(u0 + 0.5, v0), Vector2(u0, v0)]
		for k in [0, 2, 1, 0, 3, 2]:
			st.set_normal(n)
			st.set_uv(uv[k])
			st.add_vertex(p[k])
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load(ART + "textures/atlas/signs_horizontal.png")
	mat.emission_enabled = true
	mat.emission_texture = mat.albedo_texture
	mat.emission = Color.WHITE
	mat.emission_energy_multiplier = 0.45                        # backlit lightboxes, a little bloom
	mat.roughness = 0.6
	var mi := MeshInstance3D.new()
	mi.name = "MallSigns"
	mi.mesh = st.commit()
	mi.material_override = mat
	mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(mi)


## Light trim strips on the jump-out edges (roof ring both sides, top-floor slab outside): ONE mesh, 5 cm off the faces.
func _mall_trims(trims: Array) -> void:
	if trims.is_empty():
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for s in trims:
		var c := Vector3(s.pos[0], s.pos[1], s.pos[2])
		var n := Vector3(s.normal[0], 0, s.normal[2]).normalized()
		var tg := Vector3(n.z, 0, -n.x)
		var hw: float = float(s.size[0]) * 0.5
		var hh: float = float(s.size[1]) * 0.5
		var p := [c - tg * hw - Vector3.UP * hh, c + tg * hw - Vector3.UP * hh, c + tg * hw + Vector3.UP * hh, c - tg * hw + Vector3.UP * hh]
		for k in [0, 2, 1, 0, 3, 2]:
			st.set_normal(n)
			st.add_vertex(p[k])
	var mi := MeshInstance3D.new()
	mi.name = "MallEdgeTrims"
	mi.mesh = st.commit()
	mi.material_override = _role_mat("atrium_rail")
	mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(mi)


## Portrait screens flush on the outer wall (the slice's billboard), with a thin dark frame just in front of the wall.
func _mall_screens(screens: Array) -> void:
	var k := 0
	for s in screens:
		var c := Vector3(s.pos[0], s.pos[1], s.pos[2])
		var n := Vector3(s.normal[0], 0, s.normal[2]).normalized()
		var tg := Vector3(n.z, 0, -n.x)
		var w: float = s.size[0]
		var h: float = s.size[1]
		var q := QuadMesh.new()
		q.size = Vector2(w, h)
		var scr := MeshInstance3D.new()
		scr.name = "MallScreen_%d" % k
		scr.mesh = q
		scr.material_override = _screen()
		scr.position = c + n * 0.02
		scr.rotation.y = atan2(n.x, n.z)
		scr.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		scr.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_root.add_child(scr)
		var basis := Basis(tg, Vector3.UP, n)
		for e in [[Vector3(0, h * 0.5 + 0.08, 0), Vector3(w + 0.32, 0.16, 0.08)], [Vector3(0, -h * 0.5 - 0.08, 0), Vector3(w + 0.32, 0.16, 0.08)],
				[Vector3(w * 0.5 + 0.08, 0, 0), Vector3(0.16, h, 0.08)], [Vector3(-w * 0.5 - 0.08, 0, 0), Vector3(0.16, h, 0.08)]]:
			var b := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = e[1]
			bm.add_uv2 = true
			b.mesh = bm
			b.material_override = _role_mat("mullion")
			b.gi_mode = GeometryInstance3D.GI_MODE_STATIC
			b.transform = Transform3D(basis, c + basis * e[0] + n * 0.04)
			_root.add_child(b)
		k += 1
