// Fake rooms behind windows ("interior mapping"). Owner: Claude.
// The window is one flat quad with 0..1 UVs (kit material "window_room"). For every pixel we trace the view ray
// into an imaginary box room (window width x window height x room_depth) and colour the wall / floor / ceiling it hits.
// Real depth and parallax for the price of one quad. Each window gets its own look from a hash of its position:
// lights on / dim / off, warm or cool, blinds half down.
// Optional: room_atlas = a grid of painted back walls (ChatGPT, task T7); one cell per window.
shader_type spatial;
render_mode unshaded, cull_back;

uniform float room_depth = 3.0;                       // metres
uniform vec3 wall_col : source_color = vec3(0.80, 0.57, 0.36);
uniform vec3 floor_col : source_color = vec3(0.30, 0.19, 0.12);
uniform vec3 ceil_col : source_color = vec3(1.0, 0.86, 0.62);
uniform vec3 cool_tint : source_color = vec3(0.75, 0.85, 1.0);
uniform float brightness = 1.0;
uniform float lit_chance = 0.75;                      // share of windows with the light on
uniform float blinds_chance = 0.4;
uniform sampler2D room_atlas : source_color, hint_default_black, filter_linear_mipmap;
uniform float use_atlas = 0.0;                        // 1 = back walls from the atlas
uniform float atlas_cells = 4.0;                      // atlas is cells x cells
uniform float cell_min = 0.0;                         // which cells this material may pick (0-based, row by row):
uniform float cell_max = 7.0;                         //   homes 0-7 + 12-14, shops 8-11 + 15 (see textures/ATLAS_SPEC.md)

varying vec3 wpos;
varying vec3 wnor;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnor = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void fragment() {
	vec3 n = normalize(vec3(wnor.x, 0.0, wnor.z));     // windows are vertical
	vec3 up = vec3(0.0, 1.0, 0.0);
	vec3 right = normalize(cross(up, n));
	// window size in metres: solve the UV -> world mapping exactly from screen derivatives
	// (v2: the old estimate drifted per pixel at grazing angles -> each pixel picked another room = speckle noise)
	vec3 dpx = dFdx(wpos), dpy = dFdy(wpos);
	float dudx = dFdx(UV.x), dudy = dFdy(UV.x), dvdx = dFdx(UV.y), dvdy = dFdy(UV.y);
	float det = dudx * dvdy - dvdx * dudy;
	det = abs(det) < 1e-12 ? 1e-12 : det;
	vec3 Pu = (dpx * dvdy - dpy * dvdx) / det;
	vec3 Pv = (dpy * dudx - dpx * dudy) / det;
	float W = clamp(round(length(Pu) * 20.0) / 20.0, 0.3, 12.0);   // snap to 5 cm: same value on every pixel
	float H = clamp(round(length(Pv) * 20.0) / 20.0, 0.3, 8.0);
	float u = UV.x, v = 1.0 - UV.y;                      // v = 0 at the bottom
	vec3 corner = wpos - right * u * W - up * v * H;     // same for the whole window -> per-window random
	vec3 key = floor(corner * 2.0 + 0.5) + floor(NODE_POSITION_WORLD * 4.0 + 0.5) * 0.173;
	float h1 = hash(key + 0.37), h2 = hash(key + 4.1), h3 = hash(key + 9.7);
	float D = room_depth * (0.75 + 0.5 * h2);

	vec3 dir = normalize(wpos - CAMERA_POSITION_WORLD);
	vec3 r = vec3(dot(dir, right), dot(dir, up), dot(dir, -n));
	r.z = max(r.z, 0.02);
	vec3 p = vec3(u * W, v * H, 0.0);
	float tx = r.x > 0.0 ? (W - p.x) / r.x : -p.x / min(r.x, -1e-4);
	float ty = r.y > 0.0 ? (H * 1.0 - p.y) / r.y : -p.y / min(r.y, -1e-4);
	float tz = (D - p.z) / r.z;
	float t = min(tx, min(ty, tz));
	vec3 hit = p + r * t;

	vec3 col;
	if (t == tz) {                                        // back wall
		vec2 c = vec2(hit.x / W, hit.y / H);
		col = wall_col * (0.92 + 0.08 * sin(c.x * 40.0));
		col = mix(col * 0.65, col, step(0.28, c.y));          // darker lower wall
		if (use_atlas > 0.5) {
			float cell = cell_min + floor(h3 * (cell_max - cell_min + 0.999));
			vec2 inner = clamp(vec2(c.x, 1.0 - c.y), 0.01, 0.99);   // stay inside the cell (no bleed from neighbours)
			vec2 cuv = (vec2(mod(cell, atlas_cells), floor(cell / atlas_cells)) + inner) / atlas_cells;
			col = texture(room_atlas, cuv).rgb * 1.15;
		}
	} else if (t == tx) {                                 // side walls
		col = wall_col * 0.78;
	} else if (r.y < 0.0) {                               // floor (planks)
		col = floor_col * (0.85 + 0.15 * step(0.5, fract(hit.x * 3.0)));
	} else {                                              // ceiling
		col = ceil_col * 0.9;
	}
	// one ceiling lamp in the middle of the room
	vec3 lamp = vec3(W * 0.5, H - 0.05, D * 0.45);
	float d2 = dot(hit - lamp, hit - lamp);
	float light = 0.25 + 1.1 / (1.0 + d2 * 0.35);
	light *= mix(1.0, 0.55, clamp(hit.z / D, 0.0, 1.0));  // deeper = darker
	// per-window state: on / dim / off, warm or slightly cool
	float on = h1 < lit_chance ? 1.0 : (h1 < lit_chance + 0.12 ? 0.35 : 0.06);
	vec3 tint = mix(vec3(1.0), cool_tint, step(0.8, h2));
	col *= light * on * tint * brightness;
	// blinds pulled down part of the way (in front of the room)
	float blind = step(1.0 - blinds_chance, h3) * (0.3 + 0.5 * fract(h3 * 7.0));
	if (v > 1.0 - blind) {
		float sv = v * H * 12.0;
		float slat = mix(0.75 + 0.25 * step(0.25, fract(sv)), 0.9375, clamp(fwidth(sv) * 1.5, 0.0, 1.0));  // fade slats when smaller than a pixel
		col = mix(wall_col * 0.9 * slat * (0.35 + 0.65 * on), col, 0.15);
	}
	ALBEDO = col;
}
