extends SceneTree
## Self-check, step 1 (Claude, cloud): build a district scene and dump points sampled on every VISUAL triangle that
## comes near a safety volume (doorway, stair, landing). Step 2 (selfcheck.py) tests the points exactly.
##   godot --headless --path . -s res://art_pass/districts/station/selfcheck_dump.gd -- \
##     --scene=res://art_pass/districts/<d>/<d>.tscn --vols=res://<vols.json> --out=res://<points.json>
## The rebuilt old collision (OldLayoutCollision) is skipped; merged meshes are sampled too (they also hold the old
## collider boxes, selfcheck.py drops points lying on an old collider surface).
const STEP := 0.1


func _init() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		if kv.size() == 2:
			args[kv[0]] = kv[1]
	var vols: Array = JSON.parse_string(FileAccess.get_file_as_string(args.vols))
	var boxes: Array[AABB] = []
	for v in vols:
		boxes.append(AABB(Vector3(v.lo[0], v.lo[1], v.lo[2]), Vector3(v.hi[0] - v.lo[0], v.hi[1] - v.lo[1], v.hi[2] - v.lo[2])).grow(0.05))
	var s: Node = load(args.scene).instantiate()
	root.add_child(s)
	await process_frame
	var built: Node = s.get_node("Builder/Built")
	var out := []
	var n_mesh := 0
	for gi in built.find_children("*", "MeshInstance3D", true, false):
		var mi := gi as MeshInstance3D
		if mi.mesh == null or not mi.visible or str(mi.get_path()).contains("OldLayoutCollision"):
			continue
		n_mesh += 1
		var xf := mi.global_transform
		var wa: AABB = xf * mi.mesh.get_aabb()
		var near: Array[AABB] = []
		for b in boxes:
			if b.intersects(wa):
				near.append(b)
		if near.is_empty():
			continue
		var faces := mi.mesh.get_faces()
		var pts := PackedFloat32Array()
		for t in range(0, faces.size(), 3):
			var a: Vector3 = xf * faces[t]
			var b: Vector3 = xf * faces[t + 1]
			var c: Vector3 = xf * faces[t + 2]
			var ta := AABB(a, Vector3.ZERO).expand(b).expand(c)
			var hit := false
			for bx in near:
				if bx.intersects(ta.grow(0.01)):
					hit = true
					break
			if not hit:
				continue
			var n := clampi(int(maxf(a.distance_to(b), maxf(b.distance_to(c), c.distance_to(a))) / STEP) + 1, 1, 400)
			for i in n + 1:
				for j in n + 1 - i:
					var p := a + (b - a) * (float(i) / n) + (c - a) * (float(j) / n)
					pts.append_array([p.x, p.y, p.z])
		if pts.size() > 0:
			out.append({"mesh": str(mi.get_path()).get_slice("Built/", 1), "pts": Array(pts)})
	var f := FileAccess.open(args.out, FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	print("SELFCHECK dumped %d meshes near volumes (of %d visual meshes)" % [out.size(), n_mesh])
	quit()
