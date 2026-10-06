extends SceneTree
## Self-check (Claude): no ADDED visual triangle inside any inventory opening (0.6 m deep, 4 cm jambs, sill+0.05..sill+min(2,h)-0.05).
## Approximate: samples triangle corners, edge midpoints and centroid. ChatGPT's exact clipping is the real gate.
##   godot --headless --path . -s res://art_pass/tools/check_openings.gd -- --scene=res://art_pass/districts/<d>/<d>.tscn
func _init() -> void:
	var scene := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--scene="): scene = a.substr(8)
	var root: Node = load(scene).instantiate()
	root.get_node("Builder").set("standalone", false)     # added visuals only (old geometry is not ours)
	get_root().add_child(root)
	await process_frame
	await process_frame
	var b: Node = root.get_node("Builder")
	var inv: Dictionary = b.inv
	var prisms := []
	for bl in inv.get("buildings", []):
		for sd in bl.get("street_facing_sides", []):
			var nz: bool = absf(float(sd.normal_xz[1])) > 0.5
			for o in sd.openings:
				var sill: float = float(o.get("sill_y", 0.0))
				var hh: float = minf(2.0, float(o.height_m))
				var u: float = float(o.centre_xyz[0]) if nz else float(o.centre_xyz[2])
				var pl: float = float(o.centre_xyz[2]) if nz else float(o.centre_xyz[0])
				prisms.append({"id": "%s %s" % [bl.id, str(sd.normal_xz)], "nz": nz, "pl": pl, "u0": u - float(o.width_m) * 0.5 + 0.04, "u1": u + float(o.width_m) * 0.5 - 0.04, "y0": sill + 0.05, "y1": sill + hh - 0.05})
	var hits := {}
	var items := []                                      # [name, mesh, world transform]
	for mi in b.get_node("Built").find_children("*", "MeshInstance3D", true, false):
		if not str(mi.name).begins_with("Old") and mi.mesh != null:
			items.append([str(mi.name), mi.mesh, (mi as Node3D).global_transform])
	for mm in b.get_node("Built").find_children("*", "MultiMeshInstance3D", true, false):
		var m: MultiMesh = (mm as MultiMeshInstance3D).multimesh
		for k in m.instance_count:
			items.append(["%s#%d" % [mm.name, k], m.mesh, (mm as Node3D).global_transform * m.get_instance_transform(k)])
	for it in items:
		var mi_name: String = it[0]
		var mesh: Mesh = it[1]
		var xf: Transform3D = it[2]

		for s in mesh.get_surface_count():
			var arr: Array = mesh.surface_get_arrays(s)
			var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX] if arr[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			var n: int = idx.size() if idx.size() > 0 else v.size()
			for t in range(0, n, 3):
				var a: Vector3 = xf * v[idx[t] if idx.size() else t]
				var c: Vector3 = xf * v[idx[t + 1] if idx.size() else t + 1]
				var d: Vector3 = xf * v[idx[t + 2] if idx.size() else t + 2]
				for p in [a, c, d, (a + c) * 0.5, (c + d) * 0.5, (a + d) * 0.5, (a + c + d) / 3.0]:
					for pr in prisms:
						var uu: float = (p as Vector3).x if pr.nz else (p as Vector3).z
						var ww: float = (p as Vector3).z if pr.nz else (p as Vector3).x
						if (p as Vector3).y > pr.y0 and p.y < pr.y1 and uu > pr.u0 and uu < pr.u1 and absf(ww - pr.pl) < 0.3:
							var k: String = "%s | %s" % [pr.id, mi_name]
							if not hits.has(k):
								print("  first ", k, " tri ", a, c, d, " prism pl=", pr.pl, " u=", pr.u0, "..", pr.u1, " y=", pr.y0, "..", pr.y1)
							hits[k] = hits.get(k, 0) + 1
	print("CHECK openings=%d intersections=%d" % [prisms.size(), hits.size()])
	for k in hits:
		print("  HIT ", k, " samples=", hits[k])
	quit()
