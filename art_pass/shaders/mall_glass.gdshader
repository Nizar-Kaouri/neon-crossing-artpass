// Curved mall glass (Claude). Shops behind the glass come from a painted strip (textures/tiling/mall_interior.png,
// ChatGPT T20: one 4.5 m storey, tiles left-right). Mapped by angle around the mall's centre, so the curve never stretches it.
// Unshaded + glowing (the shops light themselves); a little sky reflection at grazing angles keeps it reading as glass.
shader_type spatial;
render_mode unshaded, cull_back;

uniform sampler2D strip : source_color, filter_linear_mipmap, repeat_enable;
uniform vec3 center = vec3(0.0);        // mall centre (world)
uniform float radius = 30.0;
uniform float strip_width = 18.0;       // metres of facade per repeat of the strip (2048x512 at 4.5 m high = 18 m)
uniform float storey = 4.5;             // glass height per floor
uniform float floor_step = 5.9;         // glass + band per floor
uniform float glow = 0.85;
uniform vec3 reflect_col : source_color = vec3(0.55, 0.5, 0.72);

varying vec3 wpos;
varying vec3 wnor;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnor = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 d = wpos.xz - center.xz;
	float u = atan(d.x, d.y) * radius / strip_width;
	float v = 1.0 - mod(wpos.y - center.y, floor_step) / storey;
	vec3 col = texture(strip, vec2(u, clamp(v, 0.005, 0.995))).rgb * glow;
	// T21 #3: not every shop equally bright - per bay (about 3 m) and per floor: lit / dimmer / closed
	float bay = floor(u * 6.0);
	float fl = floor((wpos.y - center.y) / floor_step);
	float h = fract(sin(bay * 12.9898 + fl * 78.233) * 43758.5453);
	col *= h < 0.15 ? 0.18 : (h < 0.45 ? 0.6 : 1.0);
	vec3 view = normalize(CAMERA_POSITION_WORLD - wpos);
	float fres = pow(1.0 - clamp(abs(dot(view, wnor)), 0.0, 1.0), 4.0);
	ALBEDO = mix(col, reflect_col, fres * 0.6);
}
