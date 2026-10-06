// Signs and noren: one cell of a painted atlas per sign. Owner: Claude.
// Pick the cell per placed sign with set_instance_shader_parameter("cell", n) (0-based, row by row).
shader_type spatial;
render_mode cull_disabled;

uniform sampler2D atlas : source_color, filter_linear_mipmap;
uniform vec2 cells = vec2(8.0, 1.0);                  // columns, rows of the atlas
uniform float glow = 0.0;                             // > 0 for backlit signs (lightboxes)
uniform float roughness_v = 0.8;
instance uniform float cell = 0.0;

void fragment() {
	float c = floor(cell);
	vec2 inner = clamp(UV, 0.005, 0.995);
	vec2 auv = (vec2(mod(c, cells.x), floor(c / cells.x)) + inner) / cells;
	vec3 col = texture(atlas, auv).rgb;
	ALBEDO = col;
	ROUGHNESS = roughness_v;
	EMISSION = col * glow;
}
