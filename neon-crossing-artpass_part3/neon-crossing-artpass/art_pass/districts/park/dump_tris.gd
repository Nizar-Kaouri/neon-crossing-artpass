extends SceneTree
## Self-check helper (Claude, cloud): builds a district scene exactly like the game does and writes every visual
## triangle in world space to <out>.bin (float32 x9 per triangle) + <out>.json (mesh name per triangle range).
## Usage (from the project root, needs a GL context for ArrayMesh data):
##   xvfb-run -a godot --rendering-driver opengl3 --path . -s res://art_pass/districts/homes/dump_tris.gd -- --scene=res://art_pass/districts/park/park.tscn --out=/tmp/park_tris
## Then: cd art_pass && python districts/park/self_check.py park /tmp/park_tris
var _frames := 0
var _scene: Node
var _out := ""


func _initialize() -> void:
	var path := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--scene="): path = a.substr(8)
		if a.begins_with("--out="): _out = a.substr(6)
	_scene = (load(path) as PackedScene).instantiate()
	root.add_child(_scene)


func _process(_d: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false
	var f := FileAccess.open(_out + ".bin", FileAccess.WRITE)
	var index := []
	var n := 0
	for mi in _scene.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.mesh == null or not m.is_visible_in_tree():
			continue
		var xf := m.global_transform
		var start := n
		for s in m.mesh.get_surface_count():
			var arr := m.mesh.surface_get_arrays(s)
			if arr.is_empty():
				continue
			var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX] if arr[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			if idx.is_empty():
				idx.resize(v.size())
				for k in v.size():
					idx[k] = k
			for k in range(0, idx.size() - 2, 3):
				for j in 3:
					var p: Vector3 = xf * v[idx[k + j]]
					f.store_float(p.x); f.store_float(p.y); f.store_float(p.z)
				n += 1
		if n > start:
			index.append([str(_scene.get_path_to(m)), start, n])
	f.close()
	var jf := FileAccess.open(_out + ".json", FileAccess.WRITE)
	jf.store_string(JSON.stringify(index))
	jf.close()
	print("TRIS %d in %d meshes -> %s" % [n, index.size(), _out])
	return true
