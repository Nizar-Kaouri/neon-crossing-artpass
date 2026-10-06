extends RefCounted
## Merges many static BoxMesh instances into one mesh per (material, 24 m cell), with a proper
## non-overlapping lightmap UV2 (shelf-packed per box face), so a district costs tens of draw calls
## instead of thousands and can still be baked. Only touches MeshInstance3D nodes that use a plain
## BoxMesh + material_override and GI_MODE_STATIC; everything else is left alone.
const TEXELS := 6.0          # lightmap texels per metre
const PAD := 2.0


static func merge(root: Node3D, cell := 24.0) -> int:
	var groups := {}
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		if not (mi.mesh is BoxMesh) or mi.material_override == null or mi.gi_mode != GeometryInstance3D.GI_MODE_STATIC:
			continue
		var t: Transform3D = root.global_transform.affine_inverse() * mi.global_transform
		var key := "%s|%d|%d" % [_sig(mi.material_override), floori(t.origin.x / cell), floori(t.origin.z / cell)]
		if not groups.has(key):
			groups[key] = {"mat": mi.material_override, "items": []}
		groups[key].items.append([t, (mi.mesh as BoxMesh).size])
		mi.get_parent().remove_child(mi)
		mi.queue_free()
	var made := 0
	for key in groups:
		var g: Dictionary = groups[key]
		var mesh := _build(g.items)
		var out := MeshInstance3D.new()
		out.name = "Merged_%d" % made
		out.mesh = mesh
		out.material_override = g.mat
		out.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		root.add_child(out)
		made += 1
	return made


## Same-looking materials share one group even if they are separate resources.
static func _sig(m: Material) -> String:
	if m is StandardMaterial3D:
		var tex: String = m.albedo_texture.resource_path if m.albedo_texture else ""
		return "%s|%s|%s|%.2f|%s" % [tex, m.albedo_color.to_html(), str(m.uv1_scale), m.metallic, str(m.uv1_triplanar)]
	return str(m.get_instance_id())


static func _build(items: Array) -> ArrayMesh:
	# 1) collect faces: [corner, axis_u, axis_v, normal] in local space, size in metres
	var faces := []
	for it in items:
		var t: Transform3D = it[0]
		var s: Vector3 = it[1] * 0.5
		var b := t.basis
		for f in [[Vector3.RIGHT, Vector3.BACK, Vector3.UP], [Vector3.LEFT, Vector3.FORWARD, Vector3.UP],
				[Vector3.UP, Vector3.RIGHT, Vector3.BACK], [Vector3.DOWN, Vector3.RIGHT, Vector3.FORWARD],
				[Vector3.BACK, Vector3.LEFT, Vector3.UP], [Vector3.FORWARD, Vector3.RIGHT, Vector3.UP]]:
			var n: Vector3 = f[0]; var u: Vector3 = f[1]; var v: Vector3 = f[2]
			var hu := absf(u.dot(s)); var hv := absf(v.dot(s)); var hn := absf(n.dot(s))
			var c := t * (n * hn)
			var wu := b * (u * hu); var wv := b * (v * hv)
			faces.append([c, wu, wv, (b * n).normalized(), wu.length() * 2.0, wv.length() * 2.0])
	# 2) shelf-pack the faces into a square lightmap
	faces.sort_custom(func(a, c): return a[5] > c[5])
	var area := 0.0
	for f in faces:
		area += (f[4] * TEXELS + PAD * 2) * (f[5] * TEXELS + PAD * 2)
	var size := maxf(64.0, ceilf(sqrt(area) * 1.15))
	var rects := []
	while true:
		rects.clear()
		var x := 0.0; var y := 0.0; var row := 0.0; var ok := true
		for f in faces:
			var w := maxf(2.0, f[4] * TEXELS) + PAD * 2; var h := maxf(2.0, f[5] * TEXELS) + PAD * 2
			if x + w > size:
				x = 0.0; y += row; row = 0.0
			if y + h > size or w > size:
				ok = false
				break
			rects.append(Rect2(x + PAD, y + PAD, w - PAD * 2, h - PAD * 2))
			x += w; row = maxf(row, h)
		if ok:
			break
		size = ceilf(size * 1.15)
	# 3) geometry
	var pos := PackedVector3Array(); var nor := PackedVector3Array(); var uv2 := PackedVector2Array()
	var tan := PackedFloat32Array(); var idx := PackedInt32Array()
	for i in faces.size():
		var f: Array = faces[i]; var r: Rect2 = rects[i]
		var c: Vector3 = f[0]; var wu: Vector3 = f[1]; var wv: Vector3 = f[2]; var n: Vector3 = f[3]
		var base := pos.size()
		var corners := [c - wu - wv, c + wu - wv, c + wu + wv, c - wu + wv]
		var uvs := [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
		for k in 4:
			pos.append(corners[k]); nor.append(n)
			uv2.append((r.position + uvs[k] * r.size) / size)
			var tu := wu.normalized()
			tan.append_array([tu.x, tu.y, tu.z, 1.0])
		# winding: front faces counter-clockwise seen from outside (Godot: clockwise = front) -> pick by normal
		if (corners[1] - corners[0]).cross(corners[2] - corners[0]).dot(n) > 0:
			idx.append_array([base, base + 2, base + 1, base, base + 3, base + 2])
		else:
			idx.append_array([base, base + 1, base + 2, base, base + 2, base + 3])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = pos; arr[Mesh.ARRAY_NORMAL] = nor; arr[Mesh.ARRAY_TANGENT] = tan
	arr[Mesh.ARRAY_TEX_UV2] = uv2; arr[Mesh.ARRAY_INDEX] = idx
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	m.lightmap_size_hint = Vector2i(int(size), int(size))
	return m


## Window / sign quads: one mesh per (material, cell). Each quad keeps its own 0..1 UVs, so the window shader still
## gives every window its own room (its per-window key comes from the UV corner, not from the node).
static func merge_quads(root: Node3D, cell := 48.0) -> int:
	var groups := {}
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		if not (mi.mesh is QuadMesh) or mi.material_override == null:
			continue
		var t: Transform3D = root.global_transform.affine_inverse() * mi.global_transform
		var key := "%d|%d|%d" % [mi.material_override.get_instance_id(), floori(t.origin.x / cell), floori(t.origin.z / cell)]
		if not groups.has(key):
			var st := SurfaceTool.new()
			st.begin(Mesh.PRIMITIVE_TRIANGLES)
			groups[key] = {"mat": mi.material_override, "st": st, "n": 0, "shadow": mi.cast_shadow, "gi": mi.gi_mode}
		(groups[key].st as SurfaceTool).append_from(mi.mesh, 0, t)
		groups[key].n += 1
		mi.get_parent().remove_child(mi)
		mi.queue_free()
	var made := 0
	for key in groups:
		var g: Dictionary = groups[key]
		var out := MeshInstance3D.new()
		out.name = "MergedQuads_%d" % made
		out.mesh = (g.st as SurfaceTool).commit()
		out.material_override = g.mat
		out.cast_shadow = g.shadow
		out.gi_mode = g.gi
		root.add_child(out)
		made += 1
	return made



## Convex / concave collider visuals ("Old<n>" ArrayMesh, probe-lit) -> one mesh per (material, cell) with flat
## per-triangle normals (smoothed hull normals shade ring segments as gradients). From the mall session, request #2.
static func merge_hulls(root: Node3D, cell := 48.0) -> int:
	var groups := {}
	for mi in root.get_children():
		if not (mi is MeshInstance3D) or not str(mi.name).begins_with("Old"):
			continue
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if not (mesh is ArrayMesh) or mi.material_override == null:
			continue
		var t: Transform3D = (mi as MeshInstance3D).transform
		var key := "%d|%d|%d" % [mi.material_override.get_instance_id(), floori(t.origin.x / cell), floori(t.origin.z / cell)]
		if not groups.has(key):
			groups[key] = {"mat": mi.material_override, "pos": PackedVector3Array(), "nor": PackedVector3Array()}
		var arr: Array = mesh.surface_get_arrays(0)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var vn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL] if arr[Mesh.ARRAY_NORMAL] != null else PackedVector3Array()
		var order := PackedInt32Array()
		if arr[Mesh.ARRAY_INDEX] != null and (arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() > 0:
			order = arr[Mesh.ARRAY_INDEX]
		else:
			order.resize(v.size())
			for k in v.size():
				order[k] = k
		var pos: PackedVector3Array = groups[key].pos
		var nor: PackedVector3Array = groups[key].nor
		for k in range(0, order.size(), 3):
			var a: Vector3 = t * v[order[k]]
			var b: Vector3 = t * v[order[k + 1]]
			var c: Vector3 = t * v[order[k + 2]]
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
