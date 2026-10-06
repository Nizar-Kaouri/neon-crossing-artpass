"""GROUND PASS (Claude, cloud): flat ground detail per district -> districts/<d>/GROUND_DETAIL.json.
Visual only, never collision. Everything is a thin box whose TOP sits 0.7 / 1.3 / 1.9 cm above the old ground:
  layer 1 (+0.7 cm)  asphalt on the drivable / central street areas, stone kerb strips at the road edge
  layer 2 (+1.3 cm)  road paint: crosswalk stripes, stop lines, centre / edge lines
  layer 3 (+1.9 cm)  manholes, gutter drain covers, repair patches, puddle marks
Layers never overlap themselves; a higher layer only overlaps a lower one (6 mm apart). Where nothing is added the
old paving stays (pavement along the building faces).

Where decals may go = the probe (ground_probe.py) over the old collision: the old ground slab (top = district level),
nothing else in the 2.2 m column above it, open sky above (underground: the tunnel ceiling is allowed), at least
0.3 m from anything standing on the ground, 1.0 m from anything covered (doorways under lintels, arcades, interiors),
outside building footprints (+0.2 m), opening prisms (1 m out), stair / landing / terrace volumes (+0.5 m), lawns and
other ground patches, panels on the floor and ground props (drain grates, tactile tiles).

Usage (from art_pass/): python tools/inventory/ground_detail.py [district ...] [--preview DIR]"""
import sys, json, math, random, os
import numpy as np
from scipy import ndimage as ndi
from ground_probe import Grid

LAYER = {1: 0.007, 2: 0.013, 3: 0.019}
THICK = 0.01
MERGE_CELL = 96.0                     # builder: one mesh per (material, 96 m cell); flat skins are cheap, draw calls are not
MARGIN = 14.0                         # probe beyond the district so roads / kerbs match the neighbours at the border

MATERIALS = {   # name: tiling texture, albedo tint, uv scale (world triplanar), roughness, metallic
    'asphalt':       {'tex': 'asphalt',       'tint': 'ffffff', 'uv': 0.25, 'rough': 0.92, 'metal': 0.0, 'why': 'road surface (#4f4d55 texture)'},
    'asphalt_patch': {'tex': 'asphalt',       'tint': 'c9c4cc', 'uv': 0.5,  'rough': 0.97, 'metal': 0.0, 'why': 'repair patches: a duller, greyer asphalt'},
    'puddle':        {'tex': 'plaster_cream', 'tint': '3c3844', 'uv': 0.5,  'rough': 0.08, 'metal': 0.0, 'why': 'puddle marks: smooth, dark, wet (asphalt grain sparkles at this roughness)'},
    'kerb':          {'tex': 'paving_stone',  'tint': 'f2f0ee', 'uv': 1.0,  'rough': 0.8,  'metal': 0.0, 'why': 'granite kerb line at the road edge'},
    'paint':         {'tex': 'plaster_cream', 'tint': 'fcffff', 'uv': 1.0,  'rough': 0.7,  'metal': 0.0, 'why': 'road paint #e8e2da-ish'},
    'iron':          {'tex': 'metal_panel',   'tint': 'a29a92', 'uv': 2.0,  'rough': 0.7,  'metal': 0.15, 'why': 'cast-iron manholes and drain covers'},
}
MAT_IDS = list(MATERIALS)

# per district: level (old ground y), probe rects, roads (pavement width "side", minimum road width), spot counts
CFG = {
    'alley':       dict(level=0.0, seed=11, spots_on_paving=True, road=dict(side=2.2, min_w=3.0, edge_line=False), spots=dict(manhole=1 / 160, cover=1 / 9, patch=1 / 120, puddle=1 / 140)),
    'crossing':    dict(level=0.0, seed=12, road=dict(side=2.0, min_w=4.0, edge_line=True), spots=dict(manhole=1 / 220, cover=1 / 10, patch=1 / 170, puddle=1 / 200), scramble=True),
    'shrine':      dict(level=0.0, seed=13, road=None, spots=dict(manhole=1 / 400, cover=0, patch=0, puddle=1 / 260)),     # shrine grounds stay stone
    'mall':        dict(level=0.0, seed=14, road=dict(side=3.0, min_w=6.0, edge_line=True), spots=dict(manhole=1 / 240, cover=1 / 10, patch=1 / 200, puddle=1 / 220)),
    'station':     dict(level=0.0, seed=15, cover_max=99.0, road=dict(side=2.0, min_w=4.5, edge_line=True), spots=dict(manhole=1 / 240, cover=1 / 10, patch=1 / 200, puddle=1 / 220)),
    'homes':       dict(level=0.0, seed=16, road=dict(side=1.0, min_w=3.0, edge_line=True), spots=dict(manhole=1 / 200, cover=1 / 10, patch=1 / 160, puddle=1 / 200)),
    'park':        dict(level=0.0, seed=17, road=None, spots=dict(manhole=1 / 500, cover=0, patch=0, puddle=1 / 300)),
    'underground': dict(level=-5.0, seed=18, road=None, allow_cover=True, rects=[[-95.0, -70.0, -62.5, 86.0]], margin=0.0,
                        spots=dict(manhole=1 / 300, cover=0, patch=0, puddle=1 / 120, wall_cover=1 / 16)),
}
INV_NAME = {d: f'districts/{d}/{d.upper()}_INVENTORY.json' for d in CFG}


# ------------------------------------------------------------------ masks -> rectangles
def rects_of(mask):
    """Disjoint axis-aligned rectangles (cell index ranges [i0, i1) x [k0, k1)) covering mask exactly."""
    out, open_ = [], {}
    nz, nx = mask.shape
    for k in range(nz + 1):
        runs = {}
        if k < nz:
            row = mask[k]
            if row.any():
                d = np.diff(np.concatenate([[0], row.view(np.int8), [0]]))
                for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
                    runs[(int(a), int(b))] = True
        nxt = {}
        for key, k0 in open_.items():
            if key in runs:
                nxt[key] = k0
            else:
                out.append((key[0], key[1], k0, k))
        for key in runs:
            if key not in nxt:
                nxt[key] = k
        open_ = nxt
    return out


def square(n):
    return np.ones((2 * n + 1, 2 * n + 1), bool)


def cheb(mask):
    """Chessboard distance in cells from each True cell to the nearest False cell (outside counts as False)."""
    return ndi.distance_transform_cdt(np.pad(mask, 1), metric='chessboard')[1:-1, 1:-1]


# ------------------------------------------------------------------ inventory exclusions
def exclusions(d, inv, level):
    """[(x0, z0, x1, z1, why)] rectangles where nothing may be added, plus building footprints."""
    ex = []
    for b in inv.get('buildings', []):
        fp = b.get('footprint', {})
        if 'centre_xz' in fp:
            cx, cz = fp['centre_xz']; w, dd = fp['width_m'], fp['depth_m']
            ex.append((cx - w / 2 - 0.2, cz - dd / 2 - 0.2, cx + w / 2 + 0.2, cz + dd / 2 + 0.2, 'building ' + str(b.get('id'))))
        for sd in b.get('street_facing_sides', []):
            n = sd.get('normal_xz', [0, 0])
            for o in sd.get('openings', []):
                c = o['centre_xyz']; hw = o['width_m'] / 2 + 0.3
                if abs(n[1]) > 0.5:
                    ex.append((c[0] - hw, min(c[2], c[2] + n[1] * 1.0) - 0.3, c[0] + hw, max(c[2], c[2] + n[1] * 1.0) + 0.3, 'opening'))
                else:
                    ex.append((min(c[0], c[0] + n[0] * 1.0) - 0.3, c[2] - hw, max(c[0], c[0] + n[0] * 1.0) + 0.3, c[2] + hw, 'opening'))
    for o in inv.get('openings', []):
        if isinstance(o, dict) and 'box' in o:
            (a, _, c), (b, _, e) = o['box']
            ex.append((a - 1.0, c - 1.0, b + 1.0, e + 1.0, 'opening ' + o.get('name', '')))
    for s in inv.get('stair_volumes', []):
        if s['max'][1] > level - 0.5 and s['min'][1] < level + 2.5:
            ex.append((s['min'][0] - 0.5, s['min'][2] - 0.5, s['max'][0] + 0.5, s['max'][2] + 0.5, 'stair volume'))
    for st in inv.get('structures', []):
        if isinstance(st, dict) and 'aabb_min' in st and any(k in str(st.get('role', '')) for k in ('stair', 'landing', 'terrace', 'ramp', 'escalator')):
            lo, hi = st['aabb_min'], st['aabb_max']
            if hi[1] > level - 0.5 and lo[1] < level + 2.5:
                ex.append((lo[0] - 0.5, lo[2] - 0.5, hi[0] + 0.5, hi[2] + 0.5, str(st['role'])))
    for p in inv.get('ground_patches', []):
        r = p['rect_xz']; ex.append((r[0] - 0.1, r[1] - 0.1, r[2] + 0.1, r[3] + 0.1, 'ground patch ' + p.get('mat', '')))
    for p in inv.get('panels', []):
        if p['c'][1] - p['s'][1] / 2 < level + 0.06 and p['s'][1] < 0.2:
            ex.append((p['c'][0] - p['s'][0] / 2 - 0.1, p['c'][2] - p['s'][2] / 2 - 0.1, p['c'][0] + p['s'][0] / 2 + 0.1, p['c'][2] + p['s'][2] / 2 + 0.1, 'floor panel'))
    props = list(inv.get('props', []))
    dress = f'districts/{d}/STREET_DRESS.json'
    if os.path.exists(dress):
        props += json.load(open(dress)).get('props', [])
    for p in props:
        y = p['pos'][1]
        if y - level < 0.3:
            if 'aabb' in p:
                (a, _, c), (b, _, e) = p['aabb']
            else:
                r = 0.6 if p['piece'].startswith('G_') else 1.0
                a, c, b, e = p['pos'][0] - r, p['pos'][2] - r, p['pos'][0] + r, p['pos'][2] + r
            ex.append((a - 0.15, c - 0.15, b + 0.15, e + 0.15, 'ground prop ' + p['piece']))
    return ex


# ------------------------------------------------------------------ the generator
class District:
    def __init__(self, d):
        self.d, self.cfg = d, CFG[d]
        self.level = self.cfg['level']
        self.rng = random.Random(self.cfg['seed'])
        self.inv = json.load(open(INV_NAME[d]))
        self.rects = self.cfg.get('rects') or json.load(open('districts/REGIONS.json'))['regions'][d]
        m = self.cfg.get('margin', MARGIN)
        bb = [min(r[0] for r in self.rects) - m, min(r[1] for r in self.rects) - m, max(r[2] for r in self.rects) + m, max(r[3] for r in self.rects) + m]
        self.g = Grid(bb, self.level).build()
        g = self.g
        X, Z = g.centres(0, g.nx, 0, g.nz)
        self.X, self.Z = X, Z
        self.own = np.zeros(X.shape, bool)
        for r in self.rects:
            self.own |= (X >= r[0]) & (X < r[2]) & (Z >= r[1]) & (Z < r[3])
        ground = np.isfinite(g.gtop) & (np.abs(g.gtop - self.level) < 0.005)
        free = ground & ~g.block
        covered = g.cover < self.level + self.cfg.get('cover_max', 6.0)                 # interiors, arcades, lintels (a 9 m sign gantry is fine)
        if not self.cfg.get('allow_cover'):
            # doorways / arcade mouths: covered walkable cells that touch open street; 1.0 m around them stays empty
            door = covered & free & ndi.binary_dilation(free & ~covered, square(1))
            near_cover = ndi.binary_dilation(door, square(10))
            free &= ~covered
        else:
            near_cover = np.zeros_like(free)
        if self.d == 'underground':                                                     # only the tunnel floors (y -5, ceiling at -1)
            free &= g.cover < self.level + 4.5
        self.ex = exclusions(d, self.inv, self.level)
        exm = np.zeros(X.shape, bool)
        for a, c, b, e, _ in self.ex:
            exm |= (X >= a) & (X <= b) & (Z >= c) & (Z <= e)
        self.street = free & ~exm & ~near_cover
        self.street = self.street & (cheb(self.street) > 3)                             # 0.3 m off anything standing
        self.items = []                                                                 # [mat, cx, cz, sx, sz, top, yaw]
        self.L = {k: np.zeros(X.shape, bool) for k in (1, 2, 3)}                         # occupancy per layer (own cells)
        self.road = np.zeros(X.shape, bool)
        self.counts = {}

    # -- helpers
    def add_mask(self, mask, mat, layer, tag):
        mask = mask & self.own
        n = 0
        for i0, i1, k0, k1 in rects_of(mask):
            x0, z0 = self.g.x0 + i0 * self.g.res, self.g.z0 + k0 * self.g.res
            sx, sz = (i1 - i0) * self.g.res, (k1 - k0) * self.g.res
            self.items.append([mat, round(x0 + sx / 2, 3), round(z0 + sz / 2, 3), round(sx, 3), round(sz, 3), round(self.level + LAYER[layer], 4), 0])
            n += 1
        self.L[layer] |= mask
        self.counts[tag] = self.counts.get(tag, 0) + n
        return n

    def rect_cells(self, cx, cz, sx, sz):
        r = self.g.res
        i0 = int(round((cx - sx / 2 - self.g.x0) / r)); i1 = int(round((cx + sx / 2 - self.g.x0) / r))
        k0 = int(round((cz - sz / 2 - self.g.z0) / r)); k1 = int(round((cz + sz / 2 - self.g.z0) / r))
        if i0 < 0 or k0 < 0 or i1 > self.g.nx or k1 > self.g.nz or i1 <= i0 or k1 <= k0:
            return None
        return i0, i1, k0, k1

    def snap(self, v):
        return round(v / self.g.res) * self.g.res

    def add_box(self, mat, layer, cx, cz, sx, sz, tag, yaw=0.0):
        self.items.append([mat, round(cx, 3), round(cz, 3), round(sx, 3), round(sz, 3), round(self.level + LAYER[layer], 4), round(yaw, 2)])
        self.counts[tag] = self.counts.get(tag, 0) + 1

    def footprint_ok(self, cells, area, layer, pad=1):
        i0, i1, k0, k1 = cells
        if not area[k0:k1, i0:i1].all() or not self.own[k0:k1, i0:i1].all():
            return False
        a, b, c, e = max(0, i0 - pad), i1 + pad, max(0, k0 - pad), k1 + pad
        for l in range(layer, 4):                                                       # never on top of the same or a higher layer
            if self.L[l][c:e, a:b].any():
                return False
        return True

    # -- roads, kerbs, edge lines
    def roads(self):
        rc = self.cfg.get('road')
        if not rc:
            return
        res = self.g.res
        # small islands (signal poles, a bench, bollards: < 8 m^2) do not push the road back, they get a kerb ring
        lab, n = ndi.label(~self.street)
        small = np.zeros_like(self.street)
        if n:
            sizes = ndi.sum(~self.street, lab, range(1, n + 1)) * res * res
            small = np.isin(lab, 1 + np.flatnonzero(sizes < 8.0))
            edge_lab = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
            small &= ~np.isin(lab, list(edge_lab))
        d_obst = cheb(self.street | small)
        core = d_obst >= int(round(rc['side'] / res))
        road = ndi.binary_opening(core, square(int(round(rc['min_w'] / res / 2)))) & self.street
        lab, n = ndi.label(road)
        if n:
            sizes = ndi.sum(road, lab, range(1, n + 1)) * res * res
            road = np.isin(lab, 1 + np.flatnonzero(sizes >= 40.0))
        self.road = road
        self.add_mask(road, 'asphalt', 1, 'asphalt')
        kerb = ndi.binary_dilation(road, square(2)) & ~road & self.street
        self.add_mask(kerb, 'kerb', 1, 'kerb')
        self.d_road = cheb(road)

    def no_lines(self):
        return getattr(self, '_no_lines', np.zeros(self.X.shape, bool))

    # -- the scramble crossing (crossing district)
    def paint_scramble(self, box, approaches, cw=4.0, bar=0.45, gap=0.45, stop_back=2.0, lane_len=24.0):
        """box = intersection [x0, z0, x1, z1]; approaches: {'n': [xa, xb], 's': [...], 'w': [za, zb], 'e': [...]} road
        width of each approach at the box edge. Crosswalks just outside the box, two diagonals inside it."""
        res = self.g.res
        x0, z0, x1, z1 = box
        nol = np.zeros(self.X.shape, bool)
        pitch = bar + gap
        # 4 straight crosswalks: bars long along the traffic, spaced across the road
        for side, (a, b) in approaches.items():
            if side in 'ns':
                zc = z0 - cw / 2 - 0.5 if side == 'n' else z1 + cw / 2 + 0.5
                nb = int((b - a - 0.6) // pitch)
                start = (a + b) / 2 - (nb - 1) * pitch / 2
                for j in range(nb):
                    x = start + j * pitch
                    self.paint_box(x - bar / 2, zc - cw / 2, x + bar / 2, zc + cw / 2, 'crosswalk stripe')
                nol |= (np.abs(self.Z - zc) < cw / 2 + 0.6) & (self.X > a - 1) & (self.X < b + 1)
            else:
                xc = x0 - cw / 2 - 0.5 if side == 'w' else x1 + cw / 2 + 0.5
                nb = int((b - a - 0.6) // pitch)
                start = (a + b) / 2 - (nb - 1) * pitch / 2
                for j in range(nb):
                    z = start + j * pitch
                    self.paint_box(xc - cw / 2, z - bar / 2, xc + cw / 2, z + bar / 2, 'crosswalk stripe')
                nol |= (np.abs(self.X - xc) < cw / 2 + 0.6) & (self.Z > a - 1) & (self.Z < b + 1)
        # 2 diagonals (corner to corner inside the box), bars across the walking direction; the 2nd skips the centre
        cxm, czm = (x0 + x1) / 2, (z0 + z1) / 2
        L = math.hypot(x1 - x0, z1 - z0) - 2.0
        placed_a = []
        for di, (ux, uz) in enumerate([((x1 - x0), (z1 - z0)), ((x1 - x0), -(z1 - z0))]):
            l = math.hypot(ux, uz); ux, uz = ux / l, uz / l
            yaw = math.degrees(math.atan2(ux, uz))                                       # box local z (its length) along u
            nb = int(L // pitch)
            for j in range(nb):
                t = -L / 2 + (j + 0.5) * pitch
                px, pz = cxm + ux * t, czm + uz * t
                if di == 1 and abs(t) < cw / 2 + bar:
                    continue                                                            # the first diagonal owns the centre
                corners = self.obb(px, pz, cw, bar, yaw)                               # bar: cw across the walk, bar along it
                if not all(x0 + 0.3 < c[0] < x1 - 0.3 and z0 + 0.3 < c[1] < z1 - 0.3 for c in corners):
                    continue
                if not self.obb_on(px, pz, cw, bar, yaw, self.road & (self.d_road >= 3)):
                    continue
                self.add_box('paint', 2, px, pz, cw, bar, 'diagonal crosswalk stripe', yaw=yaw)
                self.mark_obb(corners, 2)
        nol |= (self.X > x0 - 0.6) & (self.X < x1 + 0.6) & (self.Z > z0 - 0.6) & (self.Z < z1 + 0.6)
        # stop lines (traffic keeps left: incoming lanes are on the driver's left) + centre lines on each approach
        for side, (a, b) in approaches.items():
            mid = self.snap((a + b) / 2)
            if side == 'n':
                zs = z0 - cw - 0.5 - stop_back - bar / 2
                self.paint_box(mid + 0.2, zs - bar / 2, b + 3, zs + bar / 2, 'stop line')
                self.centre_line(mid, zs + bar / 2 + 0.3, -1, lane_len, 'z')
            elif side == 's':
                zs = z1 + cw + 0.5 + stop_back + bar / 2
                self.paint_box(a - 3, zs - bar / 2, mid - 0.2, zs + bar / 2, 'stop line')
                self.centre_line(mid, zs - bar / 2 - 0.3, 1, lane_len, 'z')
            elif side == 'w':
                xs = x0 - cw - 0.5 - stop_back - bar / 2
                self.paint_box(xs - bar / 2, a - 3, xs + bar / 2, mid - 0.2, 'stop line')
                self.centre_line(mid, xs + bar / 2 + 0.3, -1, lane_len, 'x')
            else:
                xs = x1 + cw + 0.5 + stop_back + bar / 2
                self.paint_box(xs - bar / 2, mid + 0.2, xs + bar / 2, b + 3, 'stop line')
                self.centre_line(mid, xs - bar / 2 - 0.3, 1, lane_len, 'x')
            nol |= self.L[2]
        self._no_lines = nol

    def centre_line(self, at, start, sign, length, along):
        """Solid for the first 8 m from the stop line, then 3 m dashes every 6 m (on the road only)."""
        w = 0.15
        t = 0.0
        while t < length:
            seg = 8.0 if t == 0.0 else 3.0
            a = start + sign * t; b = start + sign * (t + seg)
            c = (a + b) / 2
            if along == 'z':
                ok = self.paint_box(at - w / 2, c - seg / 2, at + w / 2, c + seg / 2, 'centre line', min_len=seg * 0.9)
            else:
                ok = self.paint_box(c - seg / 2, at - w / 2, c + seg / 2, at + w / 2, 'centre line', min_len=seg * 0.9)
            if not ok:
                break
            t += seg + (3.0 if t > 0.0 else 3.0)

    def on(self, m, x, z):
        i, k = self.g.idx(x, z)
        return 0 <= i < self.g.nx and 0 <= k < self.g.nz and bool(m[k, i])

    def obb(self, cx, cz, sx, sz, yaw):
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        ax = (c, -s); az = (s, c)                                                        # Godot yaw about +y: local x -> (cos, -sin), local z -> (sin, cos)
        return [(cx + ax[0] * u * sx / 2 + az[0] * v * sz / 2, cz + ax[1] * u * sx / 2 + az[1] * v * sz / 2) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    def obb_on(self, cx, cz, sx, sz, yaw, area):
        """Every 5 cm sample of the rotated box lies on area."""
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        for u in np.linspace(-sx / 2, sx / 2, max(2, int(sx / 0.05) + 1)):
            for v in np.linspace(-sz / 2, sz / 2, max(2, int(sz / 0.05) + 1)):
                if not self.on(area, cx + c * u + s * v, cz - s * u + c * v):
                    return False
        return True

    def mark_obb(self, corners, layer):
        xs = [c[0] for c in corners]; zs = [c[1] for c in corners]
        m = (self.X >= min(xs)) & (self.X <= max(xs)) & (self.Z >= min(zs)) & (self.Z <= max(zs))
        P = np.stack([self.X[m], self.Z[m]], -1)
        inside = np.ones(len(P), bool)
        for j in range(4):
            a = np.array(corners[j]); b = np.array(corners[(j + 1) % 4])
            inside &= ((b[0] - a[0]) * (P[:, 1] - a[1]) - (b[1] - a[1]) * (P[:, 0] - a[0])) >= -0.08
        idx = np.flatnonzero(m.ravel())[inside]
        self.L[layer].ravel()[idx] = True

    def paint_box(self, x0, z0, x1, z1, tag, min_len=0.6):
        """Paint the part of a rectangle that lies on the road (>= 0.2 m in from the kerb), clear of other paint."""
        m = (self.X >= min(x0, x1)) & (self.X < max(x0, x1)) & (self.Z >= min(z0, z1)) & (self.Z < max(z0, z1))
        m &= self.road & (self.d_road >= 3) & ~ndi.binary_dilation(self.L[2], square(1))
        if m.sum() * self.g.res ** 2 < min_len * min(abs(x1 - x0), abs(z1 - z0)):
            return False
        self.add_mask(m, 'paint', 2, tag)
        return True

    # -- spots: manholes, drain covers, repair patches, puddles
    def spots(self):
        sp = self.cfg['spots']
        res = self.g.res
        has_road = self.road.any()
        paving = self.street & (cheb(self.street) >= 10)
        base = self.road | paving if self.cfg.get('spots_on_paving') else (self.road if has_road else paving)
        base = base & self.own
        area_m2 = base.sum() * res * res
        inner = base & (cheb(base) >= 8)                                                 # 0.8 m inside the road / paving
        cand = np.argwhere(inner)
        def pick():
            k, i = cand[self.rng.randrange(len(cand))]
            return self.g.xz(i, k)
        if len(cand) == 0:
            return
        # manholes: a round lid drawn as 3 disjoint boxes (0.7 m across)
        n = int(round(area_m2 * sp['manhole']))
        for _ in range(n * 40):
            if self.counts.get('manhole', 0) >= n:
                break
            x, z = pick(); x, z = self.snap(x), self.snap(z)
            parts = [(x, z, 0.7, 0.3), (x, z - 0.25, 0.5, 0.2), (x, z + 0.25, 0.5, 0.2)]
            cells = [self.rect_cells(*p) for p in parts]
            if any(c is None for c in cells) or not all(self.footprint_ok(c, inner, 3, pad=3) for c in cells):
                continue
            for p, c in zip(parts, cells):
                self.add_box('iron', 3, *p, 'manhole part')
                i0, i1, k0, k1 = c; self.L[3][k0:k1, i0:i1] = True
            self.counts['manhole'] = self.counts.get('manhole', 0) + 1
        # gutter drain covers along the kerb, on the road side, every ~1 / cover metres of kerb
        if has_road and sp['cover']:
            band = self.road & (self.d_road >= 1) & (self.d_road <= 5) & self.own
            kerb_len = (self.road & (self.d_road == 1) & self.own).sum() * res
            n = int(round(kerb_len * sp['cover']))
            bc = np.argwhere(band & (self.d_road == 3))
            for _ in range(n * 30):
                if self.counts.get('drain cover', 0) >= n or len(bc) == 0:
                    break
                k, i = bc[self.rng.randrange(len(bc))]
                x, z = self.g.xz(i, k)
                for sx, sz in ((0.8, 0.4), (0.4, 0.8)):
                    c = self.rect_cells(self.snap(x), self.snap(z), sx, sz)
                    if c and self.footprint_ok(c, band, 3, pad=20):                     # >= 2 m between covers
                        self.add_box('iron', 3, self.snap(x), self.snap(z), sx, sz, 'drain cover')
                        i0, i1, k0, k1 = c; self.L[3][k0:k1, i0:i1] = True
                        break
        # tunnel gutters: drain covers along the walls (0.35..0.75 m off them)
        if sp.get('wall_cover'):
            ds = cheb(self.street)
            band = self.street & (ds >= 1) & (ds <= 5) & self.own
            n = int(round((self.street & (ds == 1) & self.own).sum() * res * sp['wall_cover'] / 2))
            bc = np.argwhere(band & (ds == 3))
            for _ in range(n * 30):
                if self.counts.get('drain cover', 0) >= n or len(bc) == 0:
                    break
                k, i = bc[self.rng.randrange(len(bc))]
                x, z = self.g.xz(i, k)
                for sx, sz in ((0.8, 0.4), (0.4, 0.8)):
                    c = self.rect_cells(self.snap(x), self.snap(z), sx, sz)
                    if c and self.footprint_ok(c, band, 3, pad=30):
                        self.add_box('iron', 3, self.snap(x), self.snap(z), sx, sz, 'drain cover')
                        i0, i1, k0, k1 = c; self.L[3][k0:k1, i0:i1] = True
                        break
        # repair patches: plain rectangles of duller asphalt
        n = int(round(area_m2 * sp['patch']))
        for _ in range(n * 40):
            if self.counts.get('repair patch', 0) >= n:
                break
            x, z = pick()
            sx, sz = self.snap(self.rng.uniform(0.9, 3.2)), self.snap(self.rng.uniform(0.7, 2.2))
            if self.rng.random() < 0.5:
                sx, sz = sz, sx
            c = self.rect_cells(self.snap(x), self.snap(z), sx, sz)
            if c and self.footprint_ok(c, inner, 3, pad=3) and not self.L[2][c[2]:c[3], c[0]:c[1]].any():
                self.add_box('asphalt_patch', 3, self.snap(x), self.snap(z), sx, sz, 'repair patch')
                i0, i1, k0, k1 = c; self.L[3][k0:k1, i0:i1] = True
        # puddle marks: a soft blob (union of ellipses) cut into disjoint boxes
        n = int(round(area_m2 * sp['puddle']))
        made = 0
        for _ in range(n * 40):
            if made >= n:
                break
            x, z = pick()
            R = self.rng.uniform(0.6, 1.4)
            r = int(R / res) + 4
            i, k = self.g.idx(x, z)
            if i - r < 0 or k - r < 0 or i + r >= self.g.nx or k + r >= self.g.nz:
                continue
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1] * res
            blob = np.zeros(xx.shape, bool)
            for _b in range(3):
                ox, oz = self.rng.uniform(-R * .5, R * .5), self.rng.uniform(-R * .35, R * .35)
                ax, az = R * self.rng.uniform(0.45, 0.8), R * self.rng.uniform(0.3, 0.55)
                blob |= ((xx - ox) / ax) ** 2 + ((yy - oz) / az) ** 2 <= 1
            sl = (slice(k - r, k + r + 1), slice(i - r, i + r + 1))
            pad = ndi.binary_dilation(blob, square(2))
            if (pad & ~inner[sl]).any() or (pad & self.L[3][sl]).any() or (pad & self.L[2][sl]).any() or not self.own[sl][blob].all():
                continue
            full = np.zeros(self.X.shape, bool); full[sl] = blob
            self.add_mask(full, 'puddle', 3, 'puddle box')
            made += 1
        self.counts['puddle'] = made

    def run(self):
        self.roads()
        if self.cfg.get('scramble'):
            self.scr = SCRAMBLE
            self.paint_scramble(SCRAMBLE['box'], SCRAMBLE['approaches'])
        if self.cfg.get('road') and self.cfg['road'].get('edge_line'):
            wide = ndi.binary_opening(self.road, square(int(round(3.5 / self.g.res))))
            edge = wide & (self.d_road >= 6) & (self.d_road <= 7) & ~ndi.binary_dilation(self.no_lines(), square(3)) & ~self.L[2]
            edge = ndi.binary_opening(edge, np.ones((1, 10), bool)) | ndi.binary_opening(edge, np.ones((10, 1), bool))   # no stubs < 1 m
            self.add_mask(edge, 'paint', 2, 'edge line')
        self.spots()
        return self

    def out(self):
        res = self.g.res
        area = lambda m: round(float((m & self.own).sum() * res * res), 1)
        return {
            'schema_version': 1, 'district': self.d,
            'source': 'tools/inventory/ground_detail.py (Claude, cloud ground pass) from layout_dump.json + the district inventory',
            'level_y': self.level, 'merge_cell': MERGE_CELL, 'layers_top_above_level': {str(k): v for k, v in LAYER.items()}, 'thick': THICK,
            'rules': 'flat, top 0.7-1.9 cm above the old ground, no collision, never on stairs / landings / ramps / roofs / '
                     'in buildings or doorways; same-layer boxes never overlap, layers 6 mm apart',
            'materials': MATERIALS, 'mat_ids': MAT_IDS,
            'item_format': '[mat_id, centre_x, centre_z, size_x, size_z, top_y, yaw_deg]',
            'stats': {'asphalt_m2': area(self.road), 'street_m2': area(self.street), 'counts': self.counts, 'boxes': len(self.items)},
            'scramble': getattr(self, 'scr', None),
            'items': [[MAT_IDS.index(it[0])] + it[1:] for it in self.items],
        }

    def preview(self, path):
        from PIL import Image
        img = np.zeros(self.X.shape + (3,), np.uint8)
        img[np.isfinite(self.g.gtop)] = (70, 70, 70)
        img[self.street] = (150, 140, 130)
        img[self.road] = (60, 58, 70)
        img[self.g.block] = (150, 40, 40)
        col = {'asphalt': None, 'kerb': (220, 220, 210), 'paint': (255, 255, 255), 'iron': (40, 110, 220), 'asphalt_patch': (120, 100, 140), 'puddle': (40, 200, 220)}
        for it in self.items:
            c = col[it[0]]
            if c is None:
                continue
            if it[6]:
                cs = self.obb(it[1], it[2], it[3], it[4], it[6])
                xs = [p[0] for p in cs]; zs = [p[1] for p in cs]
                m = (self.X >= min(xs)) & (self.X <= max(xs)) & (self.Z >= min(zs)) & (self.Z <= max(zs))
                m &= self.L[2]
            else:
                m = (np.abs(self.X - it[1]) < it[3] / 2) & (np.abs(self.Z - it[2]) < it[4] / 2)
            img[m] = c
        img[~self.own] = img[~self.own] // 2
        Image.fromarray(img).save(path)


# the scramble crossing of the old map (crossing district), measured from the road mask (see REPORT_GROUND.md)
# box = the open intersection between the north / south streets (x -12..1) and the west / east openings (z -16..-2),
# where the old map's X stripes were; the bench at (-3, -12) stays a small kerbed island (old collision).
SCRAMBLE = {'box': [-12.0, -16.0, 1.0, -2.0],
            'approaches': {'n': [-12.0, 1.0], 's': [-12.0, 1.0], 'w': [-16.0, -2.0], 'e': [-16.0, -2.0]}}


def main(argv):
    prev = None
    if '--preview' in argv:
        j = argv.index('--preview'); prev = argv[j + 1]; argv = argv[:j] + argv[j + 2:]
    names = argv or list(CFG)
    for d in names:
        t = District(d).run()
        o = t.out()
        json.dump(o, open(f'districts/{d}/GROUND_DETAIL.json', 'w'), separators=(',', ':'))
        print(d, json.dumps(o['stats']), 'scramble', o['scramble'])
        if prev:
            t.preview(f'{prev}/ground_{d}.png')


if __name__ == '__main__':
    main(sys.argv[1:])
