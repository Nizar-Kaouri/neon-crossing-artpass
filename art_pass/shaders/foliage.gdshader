// Foliage cards: one cell of textures/atlas/foliage.png (4 x 4) per placed plant, alpha cut-out, gentle wind. Owner: Claude.
// Choose the plant with set_instance_shader_parameter("cell", n): 0-2 shrubs, 3-5 ivy, 6-7 pine, 8-9 sakura,
// 10 monstera, 11 bamboo, 12-13 grass, 14 flowering shrub, 15 fern.
shader_type spatial;
render_mode cull_disabled;

uniform sampler2D atlas : source_color, filter_linear_mipmap;
uniform float cells = 4.0;
uniform float alpha_cut = 0.45;
uniform float wind = 0.04;                            // metres of sway at the top of a 1 m card
instance uniform float cell = 0.0;

void vertex() {
	// sway grows with height above the card's bottom (UV.y = 1 at the bottom in Godot), phase from world position
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float sway = sin(TIME * 1.3 + wp.x * 0.7 + wp.z * 0.5) * wind * (1.0 - UV.y);
	VERTEX.x += sway;
	// light the card like a round bush, not like a flat sheet: normals lean up and out
	NORMAL = normalize(mix(NORMAL, vec3(0.0, 1.0, 0.0), 0.55));
}

void fragment() {
	float c = floor(cell);
	vec2 inner = clamp(UV, 0.01, 0.99);
	vec2 auv = (vec2(mod(c, cells), floor(c / cells)) + inner) / cells;
	vec4 t = texture(atlas, auv);
	ALBEDO = t.rgb;
	ALPHA = t.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	ROUGHNESS = 0.9;
	BACKLIGHT = vec3(0.25, 0.3, 0.15);             // light shining through leaves
}
