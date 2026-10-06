extends Camera3D
## Slice viewer. Right mouse = look, WASD = move, Q/E = down/up, Shift = fast.
## R = budget resolution on/off (3D drawn at 1600 px wide, like BUDGET.md, whatever the window size).
## Cost test (look at GPU ms): 5 SSAO · 6 glow · 7 sun shadows · 8 live lamp lights · 9 fog · 0 all off/on.
## 1 = the artwork's camera, 2 = street level (player eye), 3 = overview from above. F1 = hide/show the info line.
## Command line "-- --shot=<file.png>" renders the artwork view to a file and quits (used for cloud previews).

var VIEWS := {
	KEY_1: [Vector3(0.5, 2.6, -1.0), -5.0, 0.0],
	KEY_2: [Vector3(0.0, 1.7, 4.0), -2.0, 0.0],
	KEY_3: [Vector3(28.0, 30.0, 18.0), -38.0, 50.0],
}
@export var views_file := ""                       # e.g. a district's cameras.json: keys 1-3 = its cameras 1, 5, 6
var speed := 6.0
var _yaw := 0.0
var _pitch := 0.0
var _label: Label
var _shot := ""
var _frames := 0
var _budget_res := true
var _lm: LightmapGI
var _env: Environment
var _sun: DirectionalLight3D
var _preset := "custom"
var _fx := {"SSAO": true, "glow": true, "shadows": true, "lamps": true, "fog": true}


func _ready() -> void:
	if views_file != "" and FileAccess.file_exists(views_file):
		var cams: Array = JSON.parse_string(FileAccess.get_file_as_string(views_file)).cameras
		var keys := [KEY_1, KEY_2, KEY_3]
		var pick := [0, 4, 5]
		for k in 3:
			var c: Dictionary = cams[mini(pick[k], cams.size() - 1)]
			VIEWS[keys[k]] = [Vector3(c.position[0], c.position[1], c.position[2]), c.rotation_degrees[0], c.rotation_degrees[1]]
		fov = cams[0].fov_degrees
	_go(VIEWS[KEY_1])
	_lm = get_parent().get_node_or_null("LightmapGI")
	var we := get_parent().get_node_or_null("WorldEnvironment") as WorldEnvironment
	_env = we.environment if we else null
	_sun = get_parent().get_node_or_null("Sun") as DirectionalLight3D
	if _env:
		_fx.SSAO = _env.ssao_enabled
	_fx.lamps = false                                    # the builder hides the baked lamps in the game (key 8 = show live)
	# measure the real cost: no 60 FPS cap from V-Sync, and time the GPU work of this view
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	var ui := CanvasLayer.new()
	add_child(ui)
	_label = Label.new()
	_label.position = Vector2(12, 8)
	_label.add_theme_color_override("font_shadow_color", Color.BLACK)
	ui.add_child(_label)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.substr(7)
			_label.visible = false
		elif a.begins_with("--pos="):
			var v := a.substr(6).split_floats(",")
			_go([Vector3(v[0], v[1], v[2]), v[3], v[4]])
		elif a.begins_with("--preset="):
			_set_preset.call_deferred(a.substr(9))
		elif a.begins_with("--view="):
			_go(VIEWS[KEY_1 + int(a.substr(7)) - 1])


func _go(v: Array) -> void:
	position = v[0]
	_pitch = v[1]
	_yaw = v[2]
	rotation_degrees = Vector3(_pitch, _yaw, 0)


func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_RIGHT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if e.pressed else Input.MOUSE_MODE_VISIBLE
	elif e is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= e.relative.x * 0.15
		_pitch = clampf(_pitch - e.relative.y * 0.15, -89, 89)
		rotation_degrees = Vector3(_pitch, _yaw, 0)
	elif e is InputEventKey and e.pressed and not e.echo:
		if VIEWS.has(e.keycode):
			_go(VIEWS[e.keycode])
		elif e.keycode in [KEY_5, KEY_6, KEY_7, KEY_8, KEY_9]:
			var k: String = ["SSAO", "glow", "shadows", "lamps", "fog"][e.keycode - KEY_5]
			_fx[k] = not _fx[k]
			_apply_fx()
		elif e.keycode == KEY_0:
			var on := not _fx.values().has(true)
			for k in _fx:
				_fx[k] = on
			_preset = "custom"
			_apply_fx()
		elif e.keycode == KEY_L:
			_set_preset("low")
		elif e.keycode == KEY_H:
			_set_preset("high")
		elif e.keycode == KEY_R:
			_budget_res = not _budget_res
		elif e.keycode == KEY_F1:
			_label.visible = not _label.visible


## The two budget presets (BUDGET.md "Preset definitions"). L = Low, H = High, or --preset=low|high.
func _set_preset(p: String) -> void:
	var low := p == "low"
	_preset = p
	_fx = {"SSAO": not low, "glow": true, "shadows": true, "lamps": false, "fog": true}
	_apply_fx()
	var vp := get_viewport()
	vp.msaa_3d = Viewport.MSAA_DISABLED if low else Viewport.MSAA_2X
	vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA if low else Viewport.SCREEN_SPACE_AA_DISABLED
	if _sun:
		_sun.directional_shadow_max_distance = 40.0 if low else 80.0
		_sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS if low else DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	RenderingServer.directional_shadow_atlas_set_size(2048 if low else 4096, true)


func _apply_fx() -> void:
	if _env:
		_env.ssao_enabled = _fx.SSAO
		_env.glow_enabled = _fx.glow
		_env.fog_enabled = _fx.fog
	if _sun:
		_sun.shadow_enabled = _fx.shadows
	# hiding a baked lamp removes only its live cost: its baked light stays in the lightmap
	for l in get_tree().root.find_children("*", "OmniLight3D", true, false):
		l.visible = _fx.lamps


func _process(dt: float) -> void:
	var dir := Vector3.ZERO
	if Input.is_physical_key_pressed(KEY_W): dir.z -= 1
	if Input.is_physical_key_pressed(KEY_S): dir.z += 1
	if Input.is_physical_key_pressed(KEY_A): dir.x -= 1
	if Input.is_physical_key_pressed(KEY_D): dir.x += 1
	if Input.is_physical_key_pressed(KEY_E): dir.y += 1
	if Input.is_physical_key_pressed(KEY_Q): dir.y -= 1
	var s := speed * (4.0 if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
	position += (global_basis * Vector3(dir.x, 0, dir.z) + Vector3(0, dir.y, 0)) * s * dt
	var rs := RenderingServer
	var vp := get_viewport()
	var win := vp.get_visible_rect().size
	vp.scaling_3d_scale = clampf(1600.0 / win.x, 0.25, 1.0) if _budget_res else 1.0
	var baked := _lm != null and _lm.light_data != null
	var vrid := vp.get_viewport_rid()
	_label.text = "%d FPS   %.1f ms   GPU %.1f ms   CPU %.1f ms   draw calls %d   triangles %dk   3D %dx%d%s   LIGHTMAP: %s   PRESET: %s\n%s\nL Low · H High · 1 artwork view · 2 street · 3 overview · RMB look · WASD/QE · Shift · R budget resolution · F1 hide" % [
		Engine.get_frames_per_second(), 1000.0 / maxf(1.0, Engine.get_frames_per_second()),
		rs.viewport_get_measured_render_time_gpu(vrid), rs.viewport_get_measured_render_time_cpu(vrid),
		rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME) / 1000,
		int(win.x * vp.scaling_3d_scale), int(win.y * vp.scaling_3d_scale), " (budget)" if _budget_res else "",
		"baked" if baked else "NOT BAKED", _preset.to_upper(),
		"   ".join(_fx.keys().map(func(k): return "%s %s" % [k, "on" if _fx[k] else "OFF"])) + "   (5-9 toggle, 0 all)"]
	if _shot != "":
		_frames += 1
		if _frames == 30:
			print("SHOT draw calls %d  triangles %d" % [rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
				rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)])
			get_viewport().get_texture().get_image().save_png(_shot)
			get_tree().quit()
