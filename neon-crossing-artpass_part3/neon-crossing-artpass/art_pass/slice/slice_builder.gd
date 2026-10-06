@tool
extends Node3D
## VERTICAL SLICE (Step 4): the approved artwork's scene, built from the art-pass kit. Owner: Claude.
## Old alley on the left, crosswalk in front, stairs up to stacked terraces, mall + skyline behind.
## Builds itself in the editor AND in the game (same node names every time, so a lightmap baked in the
## editor applies at runtime). To bake: open slice.tscn, select the LightmapGI node, "Bake Lightmaps".
##
## Coordinates: Godot metres, camera looks toward -Z. Kit pieces: front faces +Z, origin = bottom-left of the
## outer face, walls 0.25 m thick going back (-Z). Each building is its own Node3D whose local frame has the
## facade at z = 0 facing +Z, spanning x 0..w and going back to z = -d.

const ART := "res://art_pass/"
const TILING := ["plaster_cream", "concrete_warm", "stone_wall_blocks", "timber_planks", "roof_kawara",
	"paving_stone", "asphalt", "metal_panel"]
const TEXELS_PER_M := 8.0                       # lightmap density (12.5 cm per lightmap texel)

@export var rebuild := false:
	set(v):
		if v and is_inside_tree():
			_build()

var lib := {}                                   # piece name -> MeshInstance3D from the GLBs
var mats := {}
var _hint_done := {}
var _root: Node3D
var _count := 0
var _lib_roots: Array[Node] = []
var _mall_center := Vector3.ZERO
var _mall_R := 30.0


func _ready() -> void:
	_build()
	if not Engine.is_editor_hint():
		_runtime_cost_cuts()


## Measured on the Arc 130V (Nizar, 2026-10-06, artwork view, 1600x900): all on 16.2 ms GPU.
## SSAO 4.2 ms (and barely visible: the lightmap already darkens corners) -> off in slice.tscn.
## Live lamps 2.4 ms although their light is already baked -> hidden in the game; the bake keeps their light,
## moving things get it from the lightmap's light probes. Glow 2.8 ms -> cheaper upscale.
func _runtime_cost_cuts() -> void:
	for l in _root.find_children("*", "OmniLight3D", true, false):
		l.visible = false
	RenderingServer.environment_glow_set_use_bicubic_upscale(false)


func _exit_tree() -> void:
	for n in _lib_roots:
		n.free()
	_lib_roots.clear()
	lib.clear()


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
	_ground()
	_left_alley()
	_center_terraces()
	_right_terraces()
	_mall()
	_dressing()
	_skyline()
	_own(_root)


## LightmapGI only bakes nodes that have an owner (it skips owner-less "helper" nodes).
## Owner = this Builder node, not the scene root, so the built nodes are never saved into slice.tscn.
func _own(n: Node) -> void:
	n.owner = self
	for c in n.get_children():
		_own(c)


# ------------------------------------------------------------------ assets
func _load_libs() -> void:
	if not lib.is_empty():
		return
	for f in [ART + "kit/kit_batch1.glb", ART + "props/props_batch1.glb"]:
		var n: Node = (load(f) as PackedScene).instantiate()
		_lib_roots.append(n)
		for c in n.find_children("*", "MeshInstance3D", true, false):
			lib[c.name] = c
	for h in ["H_vending_machine", "H_stone_lantern", "H_bicycle", "H_scooter"]:
		var n: Node = (load(ART + "props/optimized/%s.glb" % h) as PackedScene).instantiate()
		_lib_roots.append(n)
		for c in n.find_children("*", "MeshInstance3D", true, false):
			lib[h] = c


func _tiling(n: String) -> Material:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(ART + "textures/tiling/%s.png" % n)
	m.normal_enabled = true
	m.normal_texture = load(ART + "kit/materials/%s_normal.png" % n)
	m.roughness = 0.85
	if n == "metal_panel":
		m.metallic = 0.4
		m.roughness = 0.5
	return m


func _mat(n: String, piece := "") -> Material:
	var key := n + "|" + piece if n in ["window_room", "sign_face", "menu_face"] else n
	if mats.has(key):
		return mats[key]
	var m: Material
	if n in TILING:
		m = _tiling(n)
	elif n == "window_room":
		var sm := ShaderMaterial.new()
		sm.shader = load(ART + "shaders/window_room.gdshader")
		sm.set_shader_parameter("room_atlas", load(ART + "textures/atlas/room_atlas.png"))
		sm.set_shader_parameter("use_atlas", 1.0)
		var shop := piece.begins_with("A_shopfront")
		sm.set_shader_parameter("cell_min", 8.0 if shop else 0.0)
		sm.set_shader_parameter("cell_max", 11.0 if shop else 7.0)
		sm.set_shader_parameter("lit_chance", 1.0 if shop else 0.9)
		sm.set_shader_parameter("blinds_chance", 0.0 if shop else 0.35)
		sm.set_shader_parameter("brightness", 1.8 if shop else 1.5)
		m = sm
	elif n == "mall_glass":
		var sm := ShaderMaterial.new()
		sm.shader = load(ART + "shaders/mall_glass.gdshader")
		sm.set_shader_parameter("strip", load(ART + "textures/tiling/mall_interior.png"))
		sm.set_shader_parameter("center", _mall_center)
		sm.set_shader_parameter("radius", _mall_R)
		m = sm
	elif n in ["sign_face", "menu_face", "noren_cloth", "foliage"]:
		var sm := ShaderMaterial.new()
		if n == "foliage":
			sm.shader = load(ART + "shaders/foliage.gdshader")
			sm.set_shader_parameter("atlas", load(ART + "textures/atlas/foliage.png"))
		else:
			sm.shader = load(ART + "shaders/sign_atlas.gdshader")
			var atlas := "signs_horizontal"; var cells := Vector2(2, 4); var glow := 0.1
			if n == "noren_cloth":
				atlas = "noren"; cells = Vector2(2, 2); glow = 0.0
			elif n == "menu_face":
				atlas = "menus"; cells = Vector2(4, 2)
			elif piece == "A_sign_vertical":
				atlas = "signs_vertical"; cells = Vector2(8, 1); glow = 0.15
			elif piece.begins_with("M_sign_lightbox"):
				glow = 0.35
			sm.set_shader_parameter("atlas", load(ART + "textures/atlas/%s.png" % atlas))
			sm.set_shader_parameter("cells", cells)
			sm.set_shader_parameter("glow", glow)
		m = sm
	else:
		var s := StandardMaterial3D.new()
		var col: Color = {"glass": Color("6b7a8c"), "window_interior": Color("f2b26a"), "paint_white": Color("e8e2da"),
			"tactile_yellow": Color("c69a3c"), "lantern_paper": Color("fccc72"), "lantern_red": Color("d8412e"),
			"lamp_glow": Color("ffd9a0"), "ceramic_dark": Color("3a3b44"), "soil": Color("2e241c"),
			"fabric_cream": Color("e6dccb")}.get(n, Color.MAGENTA)
		s.albedo_color = col
		if n == "glass":
			s.albedo_color.a = 0.3
			s.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			s.roughness = 0.08
			s.metallic = 0.4
		if n in ["window_interior", "lantern_paper", "lantern_red", "lamp_glow"]:
			s.emission_enabled = true
			s.emission = col
			s.emission_energy_multiplier = 1.4 if n == "window_interior" else 2.0
		m = s
	mats[key] = m
	return m


func _hint(mesh: Mesh) -> void:
	# lightmap size per mesh, from its surface area (needed so LightmapGI can bake it)
	if _hint_done.has(mesh) or not (mesh is ArrayMesh):
		return
	_hint_done[mesh] = true
	var area := 0.0
	for s in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(s)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		for i in range(0, idx.size(), 3):
			area += (v[idx[i + 1]] - v[idx[i]]).cross(v[idx[i + 2]] - v[idx[i]]).length() * 0.5
	var side := clampi(int(sqrt(area) * TEXELS_PER_M), 16, 512)
	(mesh as ArrayMesh).lightmap_size_hint = Vector2i(side, side)


## Place a kit / prop piece. parent: a building node (or _root), pos/rot in that node's frame.
func place(parent: Node3D, n: String, pos: Vector3, rot := 0.0, cell := -1) -> MeshInstance3D:
	var src: MeshInstance3D = lib.get(n)
	if src == null:
		push_warning("slice: missing piece " + n)
		return null
	var mi := MeshInstance3D.new()
	_count += 1
	mi.name = "%s_%d" % [n, _count]
	mi.mesh = src.mesh
	var baked := true
	for s in src.mesh.get_surface_count():
		var m := src.mesh.surface_get_material(s)
		var mn: String = m.resource_name if m else ""
		if mn.ends_with("_mat"):
			baked = false                          # Meshy hero props: own textures, lit by light probes
			continue
		if mn in ["foliage", "glass"]:
			baked = false
		if mn == "glass" and n.begins_with("M_mall_glass"):
			mn = "mall_glass"                      # lit shop floors behind the curved glass
		mi.set_surface_override_material(s, _mat(mn, n))
	if n.begins_with("F_") or n.begins_with("P_tree_trunk"):    # plants: no lightmap UVs, lit by probes
		baked = false
	if baked:
		_hint(src.mesh)
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	else:
		mi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
	mi.position = pos
	mi.rotation.y = deg_to_rad(rot)
	parent.add_child(mi)
	if cell >= 0:
		mi.set_instance_shader_parameter("cell", float(cell))
	return mi


## A big simple block (ground, terrace slabs, retaining walls): BoxMesh, world-mapped texture.
func block(n: String, center: Vector3, size: Vector3, mat_name: String, parent: Node3D = null) -> void:
	var mi := MeshInstance3D.new()
	mi.name = n
	var b := BoxMesh.new()
	b.size = size
	b.add_uv2 = true
	b.uv2_padding = 4.0
	mi.mesh = b
	var m := _tiling(mat_name)
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3(0.5, 0.5, 0.5)                    # 1 texture = 2 m
	mi.material_override = m
	mi.position = center
	mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	var side := clampi(int(sqrt(size.x * size.z + 2 * size.y * (size.x + size.z)) * TEXELS_PER_M * 0.5), 32, 1024)
	b.lightmap_size_hint = Vector2i(side, side)
	(parent if parent else _root).add_child(mi)


func building(n: String, origin: Vector3, rot: float) -> Node3D:
	var b := Node3D.new()
	b.name = n
	b.position = origin
	b.rotation.y = deg_to_rad(rot)
	_root.add_child(b)
	return b


func _light(n: String, p: Vector3, col: Color, energy: float, rng: float, parent: Node3D = null) -> void:
	var o := OmniLight3D.new()
	o.name = n
	o.light_color = col
	o.light_energy = energy
	o.omni_range = rng
	o.position = p
	o.light_bake_mode = Light3D.BAKE_STATIC                  # baked into the lightmap: no cost at runtime
	o.shadow_enabled = false
	o.light_indirect_energy = 1.5                          # more warm bounce in the bake
	(parent if parent else _root).add_child(o)


# ------------------------------------------------------------------ shells
func top_z(run: float) -> float:
	var e := deg_to_rad(28.0)
	return -0.6 * sin(e) + (run + 0.6 * cos(e)) * tan(e)


## Walls around a box building. front: Array of [piece, width] along the facade (z = 0).
func shell(b: Node3D, w: float, d: float, y: float, front: Array, side: String, back: String, side_r := "") -> void:
	var x := 0.0
	for f in front:
		place(b, f[0], Vector3(x, y, 0), 0)
		x += f[1]
	var n := int(d / 2.0)
	for i in n:
		place(b, side_r if side_r != "" else side, Vector3(w, y, -i * 2.0), 90)
		place(b, side, Vector3(0, y, -d + i * 2.0), -90)
	for i in int(w / 4.0):
		place(b, back, Vector3(w - i * 4.0, y, -d), 180)


## Alley house (2.8 m storeys), facade along +Z, gable roof with the ridge parallel to the facade.
func alley_house(n: String, origin: Vector3, rot: float, w: float, storeys: Array, shop := {}) -> Node3D:
	var d := 6.0
	var run := 3.0
	var b := building(n, origin, rot)
	for s in storeys.size():
		shell(b, w, d, s * 2.8, storeys[s], "A_wall_plaster_2m", "A_wall_plaster_4m")
	var top := storeys.size() * 2.8
	var x := 0.0
	while x < w - 0.1:
		var pw := 4.0 if w - x >= 4.0 else 2.0
		place(b, "A_roof_slope_%dm_run3m" % int(pw), Vector3(x, top, 0), 0)
		place(b, "A_roof_slope_%dm_run3m" % int(pw), Vector3(x + pw, top, -d), 180)
		x += pw
	x = 0.0
	while x < w - 0.1:
		place(b, "A_roof_ridge_2m", Vector3(x, top + top_z(run), -run), 0)
		x += 2.0
	place(b, "A_gable_end_run3m", Vector3(0, top, -d), -90)
	place(b, "A_gable_end_run3m", Vector3(w, top, 0), 90)
	place(b, "A_eave_tip", Vector3(0, top - 0.28, 0.55), 0)
	place(b, "A_eave_tip", Vector3(w, top - 0.28, 0.55), 0)
	x = 0.0
	while x < w - 0.1:                                       # layered eave: brackets under it, fascia beam on its edge
		place(b, "A_eave_brackets_2m", Vector3(x + 0.04, top - 0.53, 0.0), 0)
		place(b, "A_beam_strip_2m", Vector3(x, top - 0.46, 0.56), 0)
		x += 2.0
	if not shop.is_empty():
		place(b, "A_canopy_roof_4m", Vector3(0, 2.75, 0), 0)
		place(b, "A_noren_2_4m", Vector3(0.8, 2.3, 0.22), 0, shop.get("noren", 0))
		place(b, "A_sign_vertical", Vector3(-0.05, 0.3, 0.9), -90, shop.get("sign", 0))
		place(b, "P_ramen_counter_set", Vector3(2.0, 0, -1.5), 0)
		for lx in [0.3, 3.7]:
			place(b, shop.get("lantern", "P_lantern_paper"), Vector3(lx, 2.45, 0.95))
		_light("ShopGlow", Vector3(2.0, 1.4, 1.0), Color("ffa860"), 2.5, 7.0, b)
		if shop.get("open", false):                       # T21 #2: the counter faces the street, stools outside
			place(b, "P_ramen_counter_set", Vector3(2.0, 0, 0.55), 180)
			for sx in [0.9, 1.7, 2.5, 3.3]:
				place(b, "P_stool", Vector3(sx, 0, 1.45))
			place(b, "P_menu_board", Vector3(4.3, 0, 1.0), 0, 1)
			_light("CounterGlow", Vector3(2.0, 1.2, 0.9), Color("ffb060"), 2.0, 4.5, b)
	return b


## Modern terrace building (3.2 m storeys), flat roof terrace with glass rail, balconies on the facade.
func terrace_house(n: String, origin: Vector3, rot: float, w: float, floors: int, ground: Array, balconies: Array, side_open := false) -> Node3D:
	var d := 8.0
	var b := building(n, origin, rot)
	for f in floors:
		var front: Array = ground if f == 0 else []
		if front.is_empty():
			for i in int(w / 2.0):
				front.append(["M_window_bay_2m", 2.0])
		shell(b, w, d, f * 3.2, front, "M_wall_concrete_2m", "M_wall_concrete_4m", "M_window_bay_2m" if side_open else "")
		if side_open and f in balconies:               # balcony wraps round the corner -> the side is no longer one flat wall
			for k in int(d / 4.0):
				place(b, "M_balcony_slab_4m", Vector3(w, f * 3.2, -4.0 * k), 90)
				place(b, "M_balcony_rail_4m", Vector3(w + 1.5, f * 3.2, -4.0 * k), 90)
				place(b, "F_ivy_wall", Vector3(w + 1.55, f * 3.2 - 0.25, -1.0 - 4.0 * k), 90, 3 + (k + f) % 3)
			place(b, "P_planter_box_1m", Vector3(w + 0.8, f * 3.2, -6.5), 90)
			place(b, "F_shrub", Vector3(w + 0.8, f * 3.2 + 0.5, -6.5), 0, 14)
		if f in balconies:
			for i in int(w / 4.0):
				place(b, "M_balcony_slab_4m", Vector3(i * 4.0, f * 3.2, 0), 0)
				place(b, "M_balcony_rail_4m", Vector3(i * 4.0, f * 3.2, 1.5), 0)
				place(b, "F_ivy_wall", Vector3(i * 4.0 + 1.0 + (f % 2) * 1.5, f * 3.2 - 0.25, 1.55), 0, 3 + (i + f) % 3)
			place(b, "P_pot_round", Vector3(w - 0.7, f * 3.2, 1.0))
			place(b, "F_pot_plant", Vector3(w - 0.7, f * 3.2, 1.0), 0, 10)
	var top := floors * 3.2
	block("%s_roof" % n, b.position + Vector3(0, top - 0.15, 0) + (Basis(Vector3.UP, deg_to_rad(rot)) * Vector3(w * 0.5, 0, -d * 0.5)),
		Vector3(w if int(rot) % 180 == 0 else d, 0.3, d if int(rot) % 180 == 0 else w), "concrete_warm")
	for i in int(w / 2.0):
		place(b, "M_glass_rail_2m", Vector3(i * 2.0, top, 0.05), 0)
	place(b, "P_roof_water_tank", Vector3(w * 0.7, top, -d * 0.6))
	place(b, "P_ac_unit", Vector3(w + 0.15, 1.2, -d * 0.5), 90)
	return b


# ------------------------------------------------------------------ the scene
func _ground() -> void:
	# street level (y 0): paving plaza with the road and its crosswalk across it
	block("Ground_plaza", Vector3(1, -0.15, -4), Vector3(36, 0.3, 32), "paving_stone")
	var road := Node3D.new()                                   # T21 #6: the street recedes to the right, not straight across
	road.name = "Road"
	road.position = Vector3(1, 0, -8.5)
	road.rotation.y = deg_to_rad(12.0)
	_root.add_child(road)
	block("Ground_road", Vector3(0, -0.13, 0), Vector3(40, 0.3, 5.0), "asphalt", road)
	for i in 7:
		place(road, "G_crosswalk_stripe", Vector3(-4.5 + i * 1.0, 0.03, 1.5), 0)
	for i in 10:
		place(road, "G_curb_2m", Vector3(-10.0 + i * 2.0, 0.0, 2.5), 0)
		place(road, "G_curb_2m", Vector3(-8.0 + i * 2.0, 0.0, -2.5), 180)
	for x in [-6.5, 5.5]:
		place(road, "G_drain_grate", Vector3(x, 0.0, 2.9), 0)
	for z in range(0, 6):
		place(_root, "G_tactile_ribs_1m", Vector3(5.2, 0.005, -11.0 - z), 0)
	# level 1 terrace (y 3.2) and level 2 (y 6.4) with retaining walls in front of them
	block("Terrace1", Vector3(2.5, 1.6, -27), Vector3(33, 3.2, 14), "stone_wall_blocks")
	block("Terrace1_top", Vector3(2.5, 3.15, -27), Vector3(33, 0.1, 14), "paving_stone")
	block("Terrace2", Vector3(3.0, 3.2, -44), Vector3(36, 6.4, 20), "stone_wall_blocks")
	block("Terrace2_top", Vector3(3.0, 6.35, -44), Vector3(36, 0.1, 20), "paving_stone")


func _left_alley() -> void:
	# houses face +X (rot 90): their facade runs from origin toward -Z
	var shop := [["A_shopfront_4m", 4.0]]
	var upper := [["A_lattice_window_2m", 2.0], ["A_wall_timber_2m", 2.0]]
	alley_house("AlleyHouse0", Vector3(-7, 0, 8.5), 90, 4.0, [shop, upper], {"noren": 3, "sign": 3, "lantern": "P_lantern_red"})
	alley_house("AlleyHouse1", Vector3(-7, 0, 4), 90, 4.0, [shop, upper], {"noren": 0, "sign": 0, "open": true})
	alley_house("AlleyHouse2", Vector3(-7, 0, -0.5), 90, 4.0, [shop, upper], {"noren": 1, "sign": 1, "lantern": "P_lantern_red", "open": true})
	# the shop the artwork view actually sees up close: open counter, red lanterns (T21 #2)
	alley_house("AlleyHouse3", Vector3(-7, 0, -5.0), 90, 4.0, [shop, upper],
		{"noren": 2, "sign": 3, "lantern": "P_lantern_red", "open": true})
	alley_house("AlleyHouse4", Vector3(-7, 0, -9.5), 90, 4.0, [shop, upper], {"noren": 2, "sign": 2})
	# back of the alley, stepping up toward the terraces
	alley_house("AlleyHouse5", Vector3(-7, 3.2, -20.5), 90, 4.0, [shop, upper], {"noren": 3, "sign": 4, "lantern": "P_lantern_red"})
	alley_house("AlleyHouse6", Vector3(-7, 3.2, -25.0), 90, 4.0, [[["A_lattice_window_2m", 2.0], ["A_lattice_window_2m", 2.0]], upper])


func _center_terraces() -> void:
	# v3 (T18 review #1/#7/#8): a wide stair to the RIGHT of a planted central block, the upper flight offset
	# further right, a bridge across the upper level -> layers that recede diagonally like the painting.
	for x in [2.0, 4.0, 6.0]:                                   # 6 m wide flight, street -> level 1
		place(_root, "M_stair_flight_2m", Vector3(x, 0, -20.0 + 5.04), 0)
	for x in [4.0, 6.0]:                                        # level 1 -> level 2, offset right
		place(_root, "M_stair_flight_2m", Vector3(x, 3.2, -34.0 + 5.04), 0)
	block("StairCheek1", Vector3(1.7, 1.6, -17.5), Vector3(0.6, 3.2, 5.0), "stone_wall_blocks")
	block("StairCheek2", Vector3(3.7, 4.8, -31.5), Vector3(0.6, 3.2, 5.0), "stone_wall_blocks")
	# central block (left of the stairs): planted edge, ivy curtain, pine + sakura on top
	var cells := [0, 1, 2, 14]
	var i := 0
	for x in [-6.4, -5.4, -4.4, -3.4, -2.4, -1.4, -0.4, 0.6]:     # continuous hedge, not a row of balls
		var sh := place(_root, "F_shrub", Vector3(x, 3.2, -20.5 + 0.15 * (i % 2)), 15 * i, cells[i % 4])
		if sh:
			sh.scale = Vector3(1.6, 0.9 + 0.2 * (i % 3), 1.3)
		i += 1
	for x in [-6.0, -4.6, -3.0, -1.6, -0.2, 1.0]:                # ivy curtains down the wall
		var iv := place(_root, "F_ivy_wall", Vector3(x, 3.15, -19.85), 0, 3 + i % 3)
		if iv:
			iv.scale = Vector3(1.3, 2.2, 1.0)
		i += 1
	place(_root, "P_tree_trunk_pine", Vector3(-1.5, 3.2, -22.0), 30)
	for c in [[-0.4, 5.0, -22.1, 6], [-2.4, 5.3, -21.9, 7], [-1.0, 5.9, -22.0, 6], [-3.2, 4.8, -22.3, 7]]:
		var pc := place(_root, "F_pine_cloud", Vector3(c[0], c[1], c[2]), 0, c[3])
		if pc:
			pc.scale = Vector3(1.8, 1.4, 1.8)
	place(_root, "P_tree_trunk_pine", Vector3(-4.5, 3.2, -23.0), 0)
	for c in [[-3.8, 5.2, -22.9, 8], [-5.4, 5.6, -22.8, 9], [-4.4, 6.2, -23.0, 8], [-2.9, 5.9, -23.2, 9]]:
		var sc := place(_root, "F_sakura_cloud", Vector3(c[0], c[1], c[2]), 0, c[3])
		if sc:
			sc.scale = Vector3(1.8, 1.5, 1.8)
	for p in [Vector3(1.5, 3.2, -21.0), Vector3(3.2, 6.4, -35.0)]:
		place(_root, "P_lamp_lantern_post", p)
		_light("Light_post_%d_%d" % [int(p.x * 10), int(p.z)], p + Vector3(0, 2.4, 0), Color("ffc27a"), 3.2, 9.0)
	for x in [-5.0, -2.6, -0.2]:
		place(_root, "P_wall_lamp", Vector3(x, 1.8, -19.95), 0)
		_light("Light_wall_%d" % int(x * 10), Vector3(x, 1.8, -19.6), Color("ffb35c"), 2.2, 5.5)
	place(_root, "H_vending_machine", Vector3(0.6, 0, -19.5), 0)
	# stairs: lamps on both side walls so the steps read
	for z in [-16.0, -19.0]:
		place(_root, "P_wall_lamp", Vector3(7.95, 1.6 + (-16.0 - z) * 0.6, z), -90)
		place(_root, "P_wall_lamp", Vector3(2.05, 1.6 + (-16.0 - z) * 0.6, z), 90)
	_light("Light_stairs_low", Vector3(5.0, 1.8, -16.5), Color("ffb870"), 2.6, 6.5)
	_light("Light_stairs_high", Vector3(5.0, 4.4, -20.5), Color("ffb870"), 2.6, 6.5)
	place(_root, "P_bench_wood", Vector3(-3.0, 3.2, -25.5), 0)
	place(_root, "H_stone_lantern", Vector3(-6.0, 3.2, -24.0), 30)
	# bridge across level 2 (in front of the mall)
	block("Bridge_deck", Vector3(2.0, 9.75, -42.0), Vector3(16.0, 0.3, 3.0), "concrete_warm")
	block("Bridge_pier_L", Vector3(-5.2, 8.0, -42.0), Vector3(1.2, 3.2, 1.2), "concrete_warm")
	block("Bridge_pier_R", Vector3(9.2, 8.0, -42.0), Vector3(1.2, 3.2, 1.2), "concrete_warm")
	for k in 8:
		place(_root, "M_glass_rail_2m", Vector3(-6.0 + k * 2.0, 9.9, -40.55), 0)
	for x in [-1.0, 5.0]:
		_light("Light_bridge_%d" % int(x), Vector3(x, 9.2, -40.8), Color("ffc890"), 2.0, 7.0)
	# sakura on level 2 next to the bridge
	place(_root, "P_tree_trunk_pine", Vector3(-6.5, 6.4, -37.5), 0)
	for c in [[-5.6, 8.3, -37.4, 9], [-7.2, 8.7, -37.3, 8], [-5.9, 9.2, -37.5, 9]]:
		place(_root, "F_sakura_cloud", Vector3(c[0], c[1], c[2]), 0, c[3])


func _right_terraces() -> void:
	# buildings face -X (rot -90): facade runs from origin toward +Z
	terrace_house("Terrace_0", Vector3(8, 0, 2.5), -90, 8.0, 2,
		[["M_window_bay_2m", 2.0], ["M_glass_door_2m", 2.0], ["M_window_bay_2m", 2.0], ["M_window_bay_2m", 2.0]], [1])
	terrace_house("Terrace_A", Vector3(8, 0, -6), -90, 8.0, 1,          # one storey: sky + towers open up on the right (T21 #4)
		[["M_glass_door_2m", 2.0], ["M_window_bay_2m", 2.0], ["M_doorway_2m", 2.0], ["M_window_bay_2m", 2.0]], [])
	block("Podium_B", Vector3(12.0, 1.6, -16.0), Vector3(8.0, 3.2, 8.0), "stone_wall_blocks")
	block("Podium_C", Vector3(13.0, 4.8, -30.0), Vector3(8.0, 3.2, 8.0), "stone_wall_blocks")
	terrace_house("Terrace_B", Vector3(8, 3.2, -20), -90, 8.0, 2, [], [0, 1], true)
	terrace_house("Terrace_C", Vector3(9, 6.4, -34), -90, 8.0, 2, [], [1], true)
	place(_root, "H_scooter", Vector3(6.2, 0, -2.5), 200)
	place(_root, "M_sign_lightbox_2m", Vector3(7.75, 2.7, -3.0), -90, 5)


func _mall() -> void:
	# v2 (T18 review #1/#4): a broad curved shopping mall sweeping from behind the alley to the right,
	# cream shell (cylinder), glass floors showing the painted shops (T20), portrait screen on the exposed corner (T19).
	_mall_R = 30.0
	_mall_center = Vector3(-15.0, 6.4, -46.0 - _mall_R)   # v4: behind the alley, opening on the right (T21 #1/#4)
	for i in range(-3, 5):                                   # glass faces the street (camera bearing ~12 deg)
		var pivot := Node3D.new()
		pivot.name = "MallPivot_%d" % (i + 3)
		pivot.position = _mall_center
		pivot.rotation.y = deg_to_rad(10.0 * i)
		_root.add_child(pivot)
		var y := 0.0
		for floor in 3:
			place(pivot, "M_mall_glass_curve_10deg", Vector3(0, y, _mall_R), 0)
			place(pivot, "M_mall_band_curve_10deg", Vector3(0, y + 4.5, _mall_R), 0)
			y += 5.9
	var body := MeshInstance3D.new()
	body.name = "Mall_body"
	var cyl := CylinderMesh.new()
	cyl.top_radius = _mall_R - 0.6
	cyl.bottom_radius = _mall_R - 0.6
	cyl.height = 19.0
	cyl.radial_segments = 48
	cyl.add_uv2 = true
	cyl.lightmap_size_hint = Vector2i(512, 512)
	body.mesh = cyl
	var bm := _tiling("plaster_cream")
	bm.uv1_triplanar = true
	bm.uv1_world_triplanar = true
	bm.uv1_scale = Vector3(0.5, 0.5, 0.5)
	body.material_override = bm
	body.position = _mall_center + Vector3(0, 9.5, 0)
	body.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	_root.add_child(body)
	# portrait screen on the corner where the glass ends
	var ang := deg_to_rad(33.0)
	var out := Vector3(sin(ang), 0, cos(ang))
	var xaxis := Vector3(cos(ang), 0, -sin(ang))
	var at := _mall_center + out * (_mall_R - 0.3) + Vector3(0, 4.5, 0)
	place(_root, "M_billboard_frame_6x9m", at - xaxis * 3.0 + out * 0.3, 33.0)
	var q := QuadMesh.new()
	q.size = Vector2(5.6, 8.6)
	var scr := MeshInstance3D.new()
	scr.name = "Mall_screen"
	scr.mesh = q
	scr.material_override = _screen()
	scr.position = at + out * 0.64 + Vector3(0, 4.5, 0)
	scr.rotation.y = ang
	scr.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	scr.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(scr)
	_light("Light_mall", _mall_center + Vector3(-8.0, 4.0, _mall_R - 1.0), Color("ffcf8a"), 4.0, 22.0)
	_light("Light_mall2", _mall_center + Vector3(10.0, 4.0, _mall_R - 4.0), Color("ffcf8a"), 4.0, 22.0)
	_light("Light_screen", at + out * 3.0 + Vector3(0, 4.5, 0), Color("c070ff"), 3.0, 16.0)


func _screen() -> Material:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_texture = load(ART + "textures/atlas/billboard.png")
	m.albedo_color = Color(1.15, 1.15, 1.15)               # a bit above 1 -> soft bloom on the PC
	return m


func _dressing() -> void:
	place(_root, "H_bicycle", Vector3(-4.6, 0, 1.0), 100)
	place(_root, "P_menu_board", Vector3(-4.6, 0, -2.5), 90, 0)
	place(_root, "P_bench_wood", Vector3(-4.8, 0, -7.0), 90)
	place(_root, "P_crates_stack", Vector3(-5.2, 0, -13.5), 80)
	place(_root, "P_pot_round", Vector3(-4.8, 0, -4.2))
	place(_root, "F_pot_plant", Vector3(-4.8, 0, -4.2), 0, 10)
	for z in [7.5, 3.0, -1.5, -10.5]:
		_light("Light_lantern_%d" % int(z * 10), Vector3(-5.6, 2.1, z), Color("ffa04a"), 3.0, 6.5)
	for p in [Vector3(-4.0, 0, -12.0), Vector3(6.5, 0, -12.0), Vector3(6.0, 0, -0.5)]:
		place(_root, "P_lamp_lantern_post", p)
		_light("Light_street_%d_%d" % [int(p.x * 10), int(p.z)], p + Vector3(0, 2.4, 0), Color("ffc27a"), 3.2, 9.0)
	for p in [Vector3(4.6, 0, -15.0), Vector3(-4.0, 0, -15.0)]:
		place(_root, "P_bollard_lamp", p)
	place(_root, "P_planter_box_1m", Vector3(7.5, 0, -14.5)); place(_root, "F_shrub", Vector3(7.5, 0.5, -14.5), 0, 14)
	place(_root, "F_grass", Vector3(-5.0, 0, -16.5), 0, 12); place(_root, "F_grass", Vector3(4.0, 0, -16.6), 0, 13)
	place(_root, "P_cable_bundle_6m", Vector3(-7.0, 5.4, -3.0), 0)
	# near street (the painting's foreground): planters, tactile guide line, drain, bench, utility box
	for z in [6.0, 1.5]:
		place(_root, "P_planter_box_1m", Vector3(6.6, 0, z))
		place(_root, "F_shrub", Vector3(6.6, 0.5, z), 30, 0)
	for z in range(0, 12):
		place(_root, "G_tactile_ribs_1m", Vector3(3.2, 0.005, 9.0 - z), 0)
	place(_root, "G_drain_grate", Vector3(1.0, 0.0, 2.5), 0)
	place(_root, "P_bench_wood", Vector3(-4.9, 0, 5.0), 90)
	place(_root, "P_utility_box", Vector3(-5.0, 0, 9.2), 90)
	place(_root, "P_bin", Vector3(-5.0, 0, 3.5))
	place(_root, "P_pot_round", Vector3(-4.9, 0, 6.6)); place(_root, "F_pot_plant", Vector3(-4.9, 0, 6.6), 0, 15)
	place(_root, "P_stool", Vector3(-4.6, 0, 7.6))
	place(_root, "F_grass", Vector3(6.9, 0, 4.0), 0, 12)
	# café on the level-1 terrace (the artwork's umbrellas up on the terraces)
	place(_root, "P_terrace_umbrella", Vector3(6.0, 3.2, -25.0))
	place(_root, "P_table_cafe", Vector3(6.0, 3.2, -25.0))
	for c in [[5.2, -25.0, 90], [6.8, -25.0, -90]]:
		place(_root, "P_chair_cafe", Vector3(c[0], 3.2, c[1]), c[2])
	place(_root, "P_planter_box_1m", Vector3(-3.8, 0, -4.6)); place(_root, "F_shrub", Vector3(-3.8, 0.5, -4.6), 0, 2)
	place(_root, "P_planter_box_1m", Vector3(5.0, 0, -4.6)); place(_root, "F_shrub", Vector3(5.0, 0.5, -4.6), 0, 14)


func _skyline() -> void:
	for layer in [["far", 170.0, 75.0, Color(0.7, 0.62, 0.74)], ["", 125.0, 85.0, Color(0.52, 0.46, 0.58)]]:
		var tex: String = ART + ("skyline/skyline_cards_far.png" if layer[0] == "far" else "skyline/skyline_cards.png")
		var m := StandardMaterial3D.new()
		m.albedo_texture = load(tex)
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		m.alpha_scissor_threshold = 0.5
		m.albedo_color = layer[3]
		m.disable_fog = true                                  # our own haze tint above, not the scene fog
		for k in [-1, 0, 1]:
			var q := QuadMesh.new()
			q.size = Vector2(layer[2] * 4.0, layer[2])
			var mi := MeshInstance3D.new()
			mi.name = "Skyline_%s_%d" % [layer[0], k + 1]
			mi.mesh = q
			mi.material_override = m
			mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var ang := deg_to_rad(40.0 * k)
			var dist: float = layer[1]
			mi.position = Vector3(sin(ang) * dist, layer[2] * 0.5 - 8.0, -cos(ang) * dist)
			mi.rotation.y = -ang
			_root.add_child(mi)
