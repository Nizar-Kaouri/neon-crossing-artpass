extends Node
## Cloud test renders (no bake, gl_compatibility):
##   xvfb-run -a godot --rendering-driver opengl3 --path . res://render_cams.tscn -- \
##     --scene=res://art_pass/districts/<d>/<d>.tscn --cams=res://art_pass/districts/<d>/cameras.json --out=renders/<d>_v0
## Writes <out>_<n>.png per camera (position + rotation_degrees [pitch, yaw]) and prints draw calls per shot.
var f := 0
var i := 0
var cams := []
var cam: Camera3D
var out := "renders/shot"
func _ready() -> void:
	var scene := ""
	var cams_file := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--scene="): scene = a.substr(8)
		if a.begins_with("--cams="): cams_file = a.substr(7)
		if a.begins_with("--out="): out = a.substr(6)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://" + out.get_base_dir()))
	var s: Node = load(scene).instantiate()
	add_child(s)
	var old := s.get_node_or_null("Camera")
	if old: old.queue_free()
	cams = JSON.parse_string(FileAccess.get_file_as_string(cams_file)).cameras
	cam = Camera3D.new(); s.add_child(cam); cam.current = true
func _process(_d: float) -> void:
	f += 1
	if f % 25 == 3:
		var c: Dictionary = cams[i]
		cam.position = Vector3(c.position[0], c.position[1], c.position[2])
		cam.rotation_degrees = Vector3(c.rotation_degrees[0], c.rotation_degrees[1], 0)
		cam.fov = float(c.get("fov_degrees", 75.0)); cam.far = 600
	if f % 25 == 24:
		var p := ProjectSettings.globalize_path("res://%s_%d.png" % [out, i + 1])
		get_viewport().get_texture().get_image().save_png(p)
		print("SHOT %d draw calls %d -> %s" % [i + 1, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME), p])
		i += 1
		if i >= cams.size(): get_tree().quit()
