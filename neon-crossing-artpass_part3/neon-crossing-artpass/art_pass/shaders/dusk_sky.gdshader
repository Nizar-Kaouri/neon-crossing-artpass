// Dusk sky (Claude): blue-lavender top -> peach-pink horizon, soft clouds, warm glow where the sun sets.
shader_type sky;

uniform vec3 top_col : source_color = vec3(0.30, 0.32, 0.62);
uniform vec3 mid_col : source_color = vec3(0.62, 0.52, 0.80);
uniform vec3 horizon_col : source_color = vec3(1.0, 0.70, 0.64);
uniform vec3 ground_col : source_color = vec3(0.20, 0.17, 0.26);
uniform vec3 cloud_col : source_color = vec3(0.86, 0.62, 0.78);
uniform vec3 cloud_dark : source_color = vec3(0.42, 0.38, 0.62);
uniform float cloud_amount = 0.45;
uniform float energy = 1.0;

float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
	float s = 0.0, a = 0.5;
	for (int i = 0; i < 5; i++) { s += a * noise(p); p *= 2.03; a *= 0.5; }
	return s;
}

void sky() {
	float y = EYEDIR.y;
	vec3 col;
	if (y < 0.0) {
		col = mix(horizon_col * 0.7, ground_col, clamp(-y * 4.0, 0.0, 1.0));
	} else {
		col = mix(horizon_col, mid_col, smoothstep(0.0, 0.18, y));
		col = mix(col, top_col, smoothstep(0.15, 0.6, y));
		// clouds: projected onto a flat layer, thin near the horizon and the zenith
		vec2 cp = EYEDIR.xz / max(y, 0.04) * 1.6;
		float c = fbm(cp + vec2(3.1, 7.7));
		float band = smoothstep(0.02, 0.10, y) * (1.0 - smoothstep(0.35, 0.7, y));
		float m = smoothstep(1.0 - cloud_amount, 1.0 - cloud_amount + 0.25, c) * band;
		vec3 cc = mix(cloud_dark, cloud_col, smoothstep(0.0, 0.25, 0.3 - y) + 0.3 * fbm(cp * 2.0));
		col = mix(col, cc, m * 0.75);
	}
	// sunset glow toward the light
	if (LIGHT0_ENABLED) {
		float s = max(dot(EYEDIR, LIGHT0_DIRECTION), 0.0);
		col += vec3(1.0, 0.55, 0.35) * pow(s, 8.0) * 0.35 * (1.0 - smoothstep(0.0, 0.4, y));
	}
	COLOR = col * energy;
}
