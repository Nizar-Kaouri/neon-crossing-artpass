@tool
extends Node3D
## The OLD MAP's exact layout, rebuilt from layout_dump.json (exported from the lab by export_layout.gd).
## Every static collider becomes a grey block with the same collision, so districts can be built and
## walk-tested against the real layout without the 3 GB lab. Optionally only a region (x0, z0, x1, z1).
@export var region := Rect2(-200, -200, 400, 400)
@export var with_visuals := true
@export var hide_paths: PackedStringArray = []          # collider paths (prefixes) to leave out

var dump: Dictionary


func _ready() -> void:
	build()


func build() -> void:
	for c in get_children():
		c.free()
	dump = JSON.parse_string(FileAccess.get_file_as_string("res://art_pass/export/layout_dump.json"))
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.62, 0.62, 0.66)
	var body := StaticBody3D.new()
	body.name = "OldLayoutCollision"
	add_child(body)
	var mm := {}
	for s in dump.static:
		var xf := _xf(s.xf)
		if not region.has_point(Vector2(xf.origin.x, xf.origin.z)):
			continue
		var skip := false
		for p in hide_paths:
			if str(s.path).begins_with(p):
				skip = true
		if skip:
			continue
		var cs := CollisionShape3D.new()
		cs.transform = xf
		var shape: Shape3D
		var mesh: Mesh
		match s.type:
			"box":
				var b := BoxShape3D.new(); b.size = _v(s.size); shape = b
				var bm := BoxMesh.new(); bm.size = b.size; mesh = bm
			"convex":
				var c := ConvexPolygonShape3D.new(); c.points = _pts(s.points); shape = c
				mesh = c.get_debug_mesh()
			"concave":
				var cc := ConcavePolygonShape3D.new(); cc.set_faces(_pts(s.faces)); shape = cc
				var am := ArrayMesh.new(); var arr := []; arr.resize(Mesh.ARRAY_MAX); arr[Mesh.ARRAY_VERTEX] = _pts(s.faces)
				am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr); mesh = am
			"cylinder":
				var cy := CylinderShape3D.new(); cy.radius = s.radius; cy.height = s.height; shape = cy
				var cm := CylinderMesh.new(); cm.top_radius = s.radius; cm.bottom_radius = s.radius; cm.height = s.height; mesh = cm
			_:
				continue
		cs.shape = shape
		body.add_child(cs)
		if with_visuals and mesh:
			var mi := MeshInstance3D.new()
			mi.mesh = mesh
			mi.transform = xf
			mi.material_override = mat
			add_child(mi)


static func _xf(a: Array) -> Transform3D:
	return Transform3D(Basis(Vector3(a[0], a[1], a[2]), Vector3(a[3], a[4], a[5]), Vector3(a[6], a[7], a[8])), Vector3(a[9], a[10], a[11]))


static func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


static func _pts(a: Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	for i in range(0, a.size(), 3):
		out.append(Vector3(a[i], a[i + 1], a[i + 2]))
	return out
