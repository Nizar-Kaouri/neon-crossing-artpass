extends Node
## STEP 7 PREP (Claude): export the OLD LAB MAP's finished layout as data, so the art pass can be built
## against the exact same layout in the cloud (where the 3 GB lab can't run).
## It builds the current map exactly like "Play Rebuilt Map" does, waits until it's finished, then writes:
##   res://art_pass/export/layout_dump.json  - every static collider (shape + transform), every moving/gameplay
##                                              actor, routes, checkpoints, spawns, shop configs, district roots
##   res://art_pass/export/layout_top.png      - a 4096 x 4096 top view (orthographic, 1 px = ~4 cm)
## Nothing in the lab is changed. Run: open art_pass/export/export_layout.tscn and press F6. It closes by itself
## (about 1-2 minutes: the old map takes a while to build).

const OUT := "res://art_pass/export/"
var main: Node3D
var stats := {"static_shapes": 0, "actors": 0, "faces": 0}


func _ready() -> void:
	DisplayServer.window_set_title("Neon Crossing - exporting layout... (closes by itself)")
	Game.map = "mall_lab"
	Game.toon = false
	Game.character = "char1"
	Game.bots = 0
	main = load("res://neon_crossing/full_rebuild/runtime.tscn").instantiate()
	add_child(main)
	_export.call_deferred()


func _export() -> void:
	var t0 := Time.get_ticks_msec()
	while not (main.arena.rebuild and main.arena.rebuild.ready_for_review):
		await get_tree().physics_frame
		if Time.get_ticks_msec() - t0 > 600000:
			push_error("EXPORT: map not ready after 10 minutes")
			get_tree().quit(1)
			return
	for i in 30:
		await get_tree().physics_frame
	var world: Node3D = main.arena
	var doc := {
		"version": 1,
		"exported": Time.get_datetime_string_from_system(),
		"note": "Old lab map (neon_crossing/full_rebuild), built at runtime then dumped. Godot metres, global coordinates.",
		"spawn_point": _v(world.spawn_point),
		"spawns": [],
		"checkpoints": [],
		"routes": [],
		"shops": {},
		"roots": [],
		"static": [],
		"actors": [],
	}
	var scr: Script = world.get_script()
	while scr:
		var consts := scr.get_script_constant_map()
		if consts.has("SPAWNS"):
			for s in consts["SPAWNS"]:
				doc.spawns.append(_v(s))
			break
		scr = scr.get_base_script()
	var cps = world.get("checkpoints")
	for c in (cps if cps != null else []):
		doc.checkpoints.append({"name": str(c.get("name", "")), "at": _v(c.get("at", Vector3.ZERO)), "look": _v(c.get("look", Vector3.ZERO))})
	var rts = world.get("routes")
	for r in (rts if rts != null else []):
		doc.routes.append({"kind": str(r.get("kind", "")), "a": _v(r.get("a", Vector3.ZERO)), "b": _v(r.get("b", Vector3.ZERO)),
			"width": float(r.get("width", 0.0)), "from": _v(r.get("walk_from", Vector3.ZERO)), "to": _v(r.get("walk_to", Vector3.ZERO))})
	var nrts = world.get("new_routes")
	for r in (nrts if nrts != null else []):
		doc.routes.append({"kind": str(r.get("name", "")), "from": _v(r.get("start", Vector3.ZERO)), "to": _v(r.get("end", Vector3.ZERO)),
			"width": float(r.get("width", 0.0))})
	if FileAccess.file_exists("res://neon_crossing/shops/config.json"):
		doc.shops = JSON.parse_string(FileAccess.get_file_as_string("res://neon_crossing/shops/config.json"))
	for child in world.get_children():
		var aabb := _visual_aabb(child)
		doc.roots.append({"name": str(child.name), "script": _script_path(child), "aabb": aabb})
	_walk(world, world, doc)
	print("EXPORT: ", stats)
	var f := FileAccess.open(OUT + "layout_dump.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(doc))
	f.close()
	await _top_view(world)
	print("EXPORT DONE in %.0f s -> %slayout_dump.json + layout_top.png" % [(Time.get_ticks_msec() - t0) / 1000.0, OUT])
	get_tree().quit()


func _walk(n: Node, world: Node3D, doc: Dictionary) -> void:
	for c in n.get_children():
		if c is CollisionObject3D:
			var path := str(world.get_path_to(c))
			var is_static := c is StaticBody3D and not (c is AnimatableBody3D)
			var shapes := []
			for s in c.get_children():
				if s is CollisionShape3D and s.shape and not s.disabled:
					shapes.append(_shape(s))
			if is_static:
				for sh in shapes:
					sh["path"] = path
					sh["layer"] = c.collision_layer
					doc.static.append(sh)
					stats.static_shapes += 1
			else:
				doc.actors.append({"path": path, "class": c.get_class(), "script": _script_path(c), "xf": _xf(c.global_transform),
					"shapes": shapes, "layer": c.collision_layer})
				stats.actors += 1
		elif c.get_script() and c is Node3D and not c is CollisionObject3D:
			var sp := _script_path(c)
			if sp.contains("zip_line") or sp.contains("rope") or sp.contains("door") or sp.contains("train") or sp.contains("pickup"):
				doc.actors.append({"path": str(world.get_path_to(c)), "class": c.get_class(), "script": sp, "xf": _xf(c.global_transform), "shapes": []})
				stats.actors += 1
		_walk(c, world, doc)


func _shape(s: CollisionShape3D) -> Dictionary:
	var d := {"xf": _xf(s.global_transform)}
	var sh := s.shape
	if sh is BoxShape3D:
		d.type = "box"; d.size = _v(sh.size)
	elif sh is SphereShape3D:
		d.type = "sphere"; d.radius = sh.radius
	elif sh is CapsuleShape3D:
		d.type = "capsule"; d.radius = sh.radius; d.height = sh.height
	elif sh is CylinderShape3D:
		d.type = "cylinder"; d.radius = sh.radius; d.height = sh.height
	elif sh is ConvexPolygonShape3D:
		d.type = "convex"; d.points = _flat(sh.points)
	elif sh is ConcavePolygonShape3D:
		var faces: PackedVector3Array = sh.get_faces()
		d.type = "concave"; d.faces = _flat(faces); d.backface = sh.backface_collision; stats.faces += faces.size() / 3
	elif sh is WorldBoundaryShape3D:
		d.type = "plane"; d.normal = _v(sh.plane.normal); d.d = sh.plane.d
	elif sh is HeightMapShape3D:
		d.type = "heightmap"; d.w = sh.map_width; d.depth = sh.map_depth; d.data = Array(sh.map_data)
	else:
		d.type = sh.get_class()
	return d


func _visual_aabb(n: Node) -> Array:
	var box := AABB()
	var first := true
	for g in n.find_children("*", "GeometryInstance3D", true, false):
		if not g.is_visible_in_tree():
			continue
		var a: AABB = g.global_transform * g.get_aabb()
		if first:
			box = a; first = false
		else:
			box = box.merge(a)
	return [] if first else [_v(box.position), _v(box.size)]


func _top_view(world: Node3D) -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(4096, 4096)
	vp.world_3d = get_viewport().world_3d
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	var aabb := _visual_aabb(world)
	var centre := Vector3(0, 0, 0)
	var span := 180.0
	if aabb.size() == 2:
		var p: Array = aabb[0]
		var s: Array = aabb[1]
		centre = Vector3(p[0] + s[0] * 0.5, 0, p[2] + s[2] * 0.5)
		span = maxf(s[0], s[2]) + 4.0
		span = minf(span, 400.0)
	cam.size = span
	cam.far = 500
	cam.position = centre + Vector3(0, 200, 0)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	vp.add_child(cam)
	cam.current = true
	for i in 20:
		await RenderingServer.frame_post_draw
	vp.get_texture().get_image().save_png(OUT + "layout_top.png")
	var meta := FileAccess.open(OUT + "layout_top.json", FileAccess.WRITE)
	meta.store_string(JSON.stringify({"centre_x": centre.x, "centre_z": centre.z, "span_m": span, "pixels": 4096,
		"note": "north = -z = image top; x grows to the right"}))
	meta.close()


func _script_path(n: Node) -> String:
	var s = n.get_script()
	return s.resource_path if s else ""


func _v(p: Vector3) -> Array:
	return [snappedf(p.x, 0.001), snappedf(p.y, 0.001), snappedf(p.z, 0.001)]


func _xf(t: Transform3D) -> Array:
	var b := t.basis
	return [snappedf(b.x.x, 0.0001), snappedf(b.x.y, 0.0001), snappedf(b.x.z, 0.0001),
		snappedf(b.y.x, 0.0001), snappedf(b.y.y, 0.0001), snappedf(b.y.z, 0.0001),
		snappedf(b.z.x, 0.0001), snappedf(b.z.y, 0.0001), snappedf(b.z.z, 0.0001),
		snappedf(t.origin.x, 0.001), snappedf(t.origin.y, 0.001), snappedf(t.origin.z, 0.001)]


func _flat(a: PackedVector3Array) -> Array:
	var out := []
	for p in a:
		out.append(snappedf(p.x, 0.001)); out.append(snappedf(p.y, 0.001)); out.append(snappedf(p.z, 0.001))
	return out
