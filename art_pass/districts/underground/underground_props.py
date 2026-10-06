"""UNDERGROUND district: the tunnel from the station to the mall's lowest floor (Claude, cloud).
Run from art_pass/:  python districts/underground/underground_props.py
Writes districts/underground/UNDERGROUND_INVENTORY.json and districts/underground/old_convex_hulls.json.

Old lab map, y = floor -5, ceiling -1 (the underside of the street slabs), 4 m clear:
  north stair well (ramp 1818, x -82.75..-79.25, z -66 -> -48.5)  ->  stair room x -86..-71.5, z -68..-46
  main corridor x -82..-72 (10 m), z -46..61, two side rooms east of it (x -71.65..-63, z -35..-25 and 5..15,
  entered through 3 m gaps in the x -72 wall; their N/S doorways lead into solid ground = dead-end alcoves)
  south stair room x -94..-82, z 42..63 (ramp 1815 from the street at z 61)
  junction z 61..71: east alcove x -72..-65 (closed by the mall's oval wall), south branch x -80..-74 to z 84,
  link x -74..-65, z 78..84 into the mall's lowest floor (y -5) through the gap in the oval wall (x -65, z 76..86).
The plain foundation slabs (y -5..-1 and -1..0) are NOT tunnel structures, except where they form the ceiling."""
import sys
sys.path.insert(0, 'districts/station')
from dresslib import *          # noqa: F401,F403
import numpy as np

RECT = (-95.0, -70.0, -62.5, 86.0)                   # x0 z0 x1 z1 (tunnel + stair wells + side rooms + mall link)
OUT = 'districts/underground/UNDERGROUND_INVENTORY.json'
RES = 0.25

near = [sh for sh in SHAPES if sh.hi[0] >= RECT[0] - 1 and sh.lo[0] <= RECT[2] + 1 and sh.hi[2] >= RECT[1] - 1 and sh.lo[2] <= RECT[3] + 1]
xs = np.arange(RECT[0] + RES / 2, RECT[2], RES)
zs = np.arange(RECT[1] + RES / 2, RECT[3], RES)
X, Z = np.meshgrid(xs, zs)


def grid_open(y):
    P = np.stack([X.ravel(), np.full(X.size, y), Z.ravel()], 1)
    return ~solid_at(P, shapes=[s for s in near if s.lo[1] <= y <= s.hi[1]]).reshape(X.shape)


OPEN = grid_open(-3.0)                                   # walkable tunnel space at chest height
OPEN_HEAD = grid_open(-1.3)                              # just under the ceiling (lintels at -2.3..-0.8 close doors here)


def open_at(x, z, g=OPEN):
    i, j = int((z - RECT[1]) / RES), int((x - RECT[0]) / RES)
    return 0 <= i < g.shape[0] and 0 <= j < g.shape[1] and bool(g[i, j])


def any_open_over(sh, g=OPEN):
    m = (X >= sh.lo[0]) & (X <= sh.hi[0]) & (Z >= sh.lo[2]) & (Z <= sh.hi[2])
    return bool((g & m).any())


# ------------------------------------------------------------------ structures with roles
ROLE_IDS = {
    'stair_flight': [1815, 1818],
    'stair_landing': [1816, 1817, 1819, 1820],           # 1816/1819 street level (top y 0), 1817/1820 tunnel floor
    'tunnel_wall': [1821, 1822, 1823, 1826, 1827, 1828, 1897, 1898, 1899, 1883, 1884, 1886, 1887, 1889, 1890, 1891, 1893, 1894, 1896],
    'door_lintel': [1885, 1888, 1892, 1895],             # dead-end doorways of the side rooms, 2.6 x 2.7 m
    'mall_link_floor': [8305, 8307, 8309], 'mall_link_ceiling': [8306, 8308, 8310],
    'mall_link_wall': [8311, 8312, 8313, 8314],          # 8313/8314 narrow the south branch to x -80..-74 from z 59
    'mall_link_bench': [8393, 8394, 8395, 8396, 8397],
    'mall_oval_wall_gap_lintel': [8015, 8016, 8017, 8018],
}
known = {i for ids in ROLE_IDS.values() for i in ids}
for sh in near:
    if sh.i in known or not is_slab(sh):
        continue
    cx, cz = (sh.lo[0] + sh.hi[0]) / 2, (sh.lo[2] + sh.hi[2]) / 2
    if abs(sh.lo[1] + 6) < 0.05 and any_open_over(sh):
        ROLE_IDS.setdefault('tunnel_floor', []).append(sh.i)
    elif abs(sh.lo[1] + 1) < 0.05 and abs(sh.hi[1]) < 0.05 and any_open_over(sh):
        ROLE_IDS.setdefault('tunnel_ceiling', []).append(sh.i)
structures = []
for role, ids in ROLE_IDS.items():
    for i in sorted(set(ids)):
        e = entry(i, role)
        if role == 'stair_flight':
            e.update(stair_axis(i))
        structures.append(e)

# openings that must stay visually empty from floor to +2.05 m (self-check volumes)
openings = [
    {'name': 'side room N gap (x -72 wall)', 'box': [[-72.6, -5.0, -31.5], [-71.4, -2.95, -28.5]]},
    {'name': 'side room S gap (x -72 wall)', 'box': [[-72.6, -5.0, 8.5], [-71.4, -2.95, 11.5]]},
]
for i in (1885, 1888, 1892, 1895):                       # lintel boxes -> doorway below them
    sh = BY_I[i]
    openings.append({'name': 'dead-end doorway under lintel %d' % i, 'box': [[sh.lo[0], -5.0, sh.lo[2] - 0.3], [sh.hi[0], -2.95, sh.hi[2] + 0.3]]})
openings.append({'name': 'mall oval wall gap', 'box': [[-65.4, -5.0, 76.3], [-64.0, -2.95, 85.7]]})
openings.append({'name': 'corridor -> south branch', 'box': [[-80.0, -5.0, 70.4], [-74.0, -2.95, 71.6]]})


# ------------------------------------------------------------------ dressing
def ceiling_at(x, z):
    """Bottom of the ceiling over (x, z), or None (stair wells are open to the sky)."""
    c = [sh.lo[1] for sh in near if sh.lo[0] <= x <= sh.hi[0] and sh.lo[2] <= z <= sh.hi[2] and -1.05 <= sh.lo[1] <= -0.5]
    return min(c) if c else None


props, district_lights, panels = [], [], []
# 1) warm paper lanterns down the middle of the corridor, the south branch and the link (bottom >= 3.3 m above floor)
lantern_pts = [(-77.0, float(z)) for z in np.arange(-43.0, 60.0, 6.5)] + [(-77.0, 66.0), (-77.0, 73.0), (-77.0, 80.5), (-70.0, 81.0)]
lantern_pts += [(-67.3, -30.0), (-67.3, 10.0), (-88.0, 44.0)]
for x, z in lantern_pts:
    cy = ceiling_at(x, z)
    if cy is None or not open_at(x, z):
        continue
    cy -= 0.05                                           # under the (requested) ceiling panel
    props.append(prop('P_lantern_paper', [x, cy, z], why='hangs from the ceiling, bottom %.2f m above the floor' % (cy - 0.63 + 5.0)))
    district_lights.append({'p': [x, cy - 0.9, z], 'col': 'ffb867', 'e': 1.2, 'r': 6.0})


# 2) wall lamps + posters + signs on the tunnel walls. Wall faces are found exactly (solid test every 1 cm),
#    so lamps sit 5 cm off the real face whether it is a wall box (x -81.65 / -72.35) or a slab edge (x -82).
SOLID_Y = [s for s in near if s.lo[1] <= -3.0 <= s.hi[1] and s.t != 'concave']


def find_face(x, z, n, y=-3.0, reach=3.0):
    """From an open point (x, z) walk against n until solid: returns (x_face, z_face) or None."""
    for k in range(int(reach / 0.01)):
        px, pz = x - n[0] * k * 0.01, z - n[1] * k * 0.01
        if solid_at([px, y, pz], shapes=SOLID_Y)[0]:
            return (round(px + n[0] * 0.005, 3), round(pz + n[1] * 0.005, 3))
    return None


def wall_ok(x, z, n, half):
    """A continuous wall face under [-half, +half] along the wall at this spot (no gap, no opening)."""
    t = (-n[1], n[0])
    f0 = find_face(x, z, n)
    if f0 is None:
        return None
    for d in np.linspace(-half, half, 5):
        f = find_face(x + t[0] * d, z + t[1] * d, n)
        if f is None or abs((f[0] - f0[0]) * n[0] + (f[1] - f0[1]) * n[1]) > 0.02:
            return None
    return f0


for xi, n in ((-79.0, (1, 0)), (-75.0, (-1, 0))):         # west wall (faces +x), east wall (faces -x)
    for k, z in enumerate(np.arange(-40.0, 60.0, 8.0)):
        z = float(z)
        f = wall_ok(xi, z, n, 0.5)
        if f is None:
            continue
        props.append(wall_mount('P_wall_lamp', f[0], -2.5, f[1], n, why='corridor wall lamp, 2.5 m above the floor'))
        if k % 3 == 1:                                    # poster triplets between lamps, eye level, 5 cm off the wall
            for dz in (-2.6, -2.0, -1.4):
                g = wall_ok(xi, z + dz, n, 0.3)
                if g is not None:
                    props.append(wall_mount('P_poster', g[0], -3.55, g[1], n, cell=(k * 3 + int(-dz * 5)) % 8, why='poster, eye level'))


def sign(x, z, n, cell, why):
    f = wall_ok(x, z, n, 1.05)
    if f is None:
        print('no wall for sign', x, z, n, why)
        return
    props.append(wall_piece('M_sign_lightbox_2m', f, n, 2.0, -2.75, 0.05, 0.52, depth_back=0.22, cell=cell, why=why))
    district_lights.append({'p': [f[0] + n[0] * 0.8, -2.4, f[1] + n[1] * 0.8], 'col': 'ffd2a0', 'e': 0.8, 'r': 4.0})


sign(-75.0, -38.0, (-1, 0), 6, 'way-finding: station platforms (north stairs)')
sign(-79.0, -20.0, (1, 0), 3, 'way-finding: mall (south)')
sign(-79.0, 30.0, (1, 0), 3, 'way-finding: mall (south)')
sign(-75.0, 50.0, (-1, 0), 6, 'way-finding: station (north)')
sign(-79.0, 68.5, (1, 0), 1, 'south branch: "mall B1" over the bench')
sign(-76.0, 82.0, (0, -1), 1, 'end of the south branch, facing back up the tunnel')
sign(-66.0, -30.0, (-1, 0), 4, 'side room back wall')
sign(-66.0, 10.0, (-1, 0), 4, 'side room back wall')
sign(-84.0, -47.5, (0, -1), 6, 'north stair room: corridor this way (seen coming down the stairs)')
sign(-88.0, 43.5, (0, 1), 6, 'south stair room wall, seen coming down the stairs')

# 3) tactile dots at the stair feet and at the mall entrance (flush on the floor, outside the landings)
for k in range(4):                                       # north stair foot: landing 1820 ends at z -48.05
    props.append(prop('G_tactile_dots_1m', [-81.75 + k * 0.875, -4.995, -47.5], 90.0, why='stair foot dots'))
for k in range(4):                                       # south stair foot: landing 1817 starts at z 45.05
    props.append(prop('G_tactile_dots_1m', [-89.0 + k * 1.0, -4.995, 44.8], 90.0, why='stair foot dots'))
for k in range(6):                                       # mall entrance (rot 0: piece spans x pos..pos+0.3, z pos-1..pos)
    props.append(prop('G_tactile_dots_1m', [-66.2, -4.995, 77.6 + k * 1.2], 0.0, why='mall entrance dots'))

# 4) (no floor props: corner plants were tried and dropped, every tunnel floor counts as walkable)


# 5) builder request R1 (preview only): tile cladding panels 5 cm off every wall face, from the open grid
def runs(mask_line):
    out, i = [], 0
    while i < len(mask_line):
        if mask_line[i]:
            j = i
            while j < len(mask_line) and mask_line[j]:
                j += 1
            out.append((i, j)); i = j
        else:
            i += 1
    return out


TH, OFF = 0.02, 0.05
for axis in ('x', 'z'):
    g = OPEN if axis == 'x' else OPEN.T
    coords_a = xs if axis == 'x' else zs                 # across the wall
    coords_b = zs if axis == 'x' else xs                 # along the wall
    for d in (1, -1):                                    # wall on the -d side of an open cell
        sh_ = np.roll(g, d, axis=1)
        edge = g & ~sh_
        if d == 1: edge[:, 0] = False
        else: edge[:, -1] = False
        for j in range(edge.shape[1]):
            for i0, i1 in runs(edge[:, j]):
                if i1 - i0 < 3:
                    continue
                b0, b1 = coords_b[i0] - RES / 2, coords_b[i1 - 1] + RES / 2
                mid = (coords_b[i0] + coords_b[i1 - 1]) / 2
                nn = (d, 0) if axis == 'x' else (0, d)
                f = find_face(coords_a[j], mid, nn) if axis == 'x' else find_face(mid, coords_a[j], nn)
                if f is None:
                    continue
                a = (f[0] if axis == 'x' else f[1]) + d * (OFF + TH / 2)
                bc, bl = (b0 + b1) / 2, b1 - b0
                for y0, y1, tint, uv, why in ((-4.99, -3.8, 'b07a5c', 2.0, 'wall tiles, terracotta dado'), (-3.8, -1.06, 'f1e6d2', 1.0, 'wall tiles, cream')):
                    c = [a, (y0 + y1) / 2, bc] if axis == 'x' else [bc, (y0 + y1) / 2, a]
                    sz = [TH, y1 - y0, bl] if axis == 'x' else [bl, y1 - y0, TH]
                    panels.append({'c': R(c), 's': R(sz), 'mat': 'paving_stone', 'tint': tint, 'uv': uv, 'why': why})
def hits_opening(c, sz):
    for o in openings:
        lo, hi = o['box']
        if all(c[k] + sz[k] / 2 > lo[k] and c[k] - sz[k] / 2 < hi[k] for k in range(3)):
            return True
    return False


# keep off the mall's oval hall (mall district) and out of every opening
def hits_stair(c, sz):
    """Panel box overlaps a stair flight / landing footprint (the ramp is solid at chest height, so the open grid
    sees its sides as walls; nothing may stand there)."""
    for e in structures:
        if e['role'] not in ('stair_flight', 'stair_landing'):
            continue
        lo, hi = e['aabb_min'], e['aabb_max']
        if c[0] + sz[0] / 2 > lo[0] - 0.05 and c[0] - sz[0] / 2 < hi[0] + 0.05 and c[2] + sz[2] / 2 > lo[2] - 0.05 and c[2] - sz[2] / 2 < hi[2] + 0.05 \
                and c[1] - sz[1] / 2 < hi[1] + 2.0:
            return True
    return False


panels = [p for p in panels if not hits_opening(p['c'], p['s']) and not hits_stair(p['c'], p['s'])
          and not (p['c'][0] > -64.9 and p['c'][2] > 50.0)]
# ceiling panels 5 cm under each ceiling slab, clipped to the open cells below it (dark warm metal)
for e in structures:
    if e['role'] not in ('tunnel_ceiling', 'mall_link_ceiling'):
        continue
    sh = BY_I[e['dump_index']]
    m = OPEN & (X >= sh.lo[0]) & (X <= sh.hi[0]) & (Z >= sh.lo[2]) & (Z <= sh.hi[2])
    if not m.any():
        continue
    x0, x1 = max(X[m].min() - RES / 2, sh.lo[0]), min(X[m].max() + RES / 2, sh.hi[0])
    z0, z1 = max(Z[m].min() - RES / 2, sh.lo[2]), min(Z[m].max() + RES / 2, sh.hi[2])
    if z1 > 50.0:
        x1 = min(x1, -64.95)                             # stop at the mall's oval wall
    if x1 - x0 < 0.3:
        continue
    panels.append({'c': R([(x0 + x1) / 2, sh.lo[1] - 0.06, (z0 + z1) / 2]), 's': R([x1 - x0, 0.02, z1 - z0]), 'mat': 'metal_panel',
                   'tint': '8a7a70', 'uv': 0.5, 'why': 'ceiling panel'})
# tactile rib guide line down the corridor centre (one thin box per straight run)
panels.append({'c': [-77.0, -4.995, 7.0], 's': [0.3, 0.01, 104.0], 'mat': 'plaster_cream', 'tint': 'c69a3c', 'uv': 2.0, 'why': 'tactile guide line'})
panels.append({'c': [-77.0, -4.995, 70.0], 's': [0.3, 0.01, 12.0], 'mat': 'plaster_cream', 'tint': 'c69a3c', 'uv': 2.0, 'why': 'tactile guide line'})
panels.append({'c': [-71.0, -4.995, 81.0], 's': [12.0, 0.01, 0.3], 'mat': 'plaster_cream', 'tint': 'c69a3c', 'uv': 2.0, 'why': 'tactile guide line'})

inv = {'schema_version': 1, 'district': 'underground',
       'source': 'layout_dump.json (Claude, cloud: districts/underground/underground_props.py)',
       'region': {'x': [RECT[0], RECT[2]], 'z': [RECT[1], RECT[3]], 'y': [-5.36, 0.0]},
       'buildings': [], 'structures': structures, 'props': props, 'openings': openings,
       'lights_in_or_affecting_region': [],               # the builder only accepts lights at y 0.5..7: see district_lights
       'district_lights': district_lights, 'panels': panels,
       'known_limits': 'district_lights and panels need builder requests R1/R2; the shared builder ignores them'}
save(inv, OUT)
hulls((RECT[0] - 1, RECT[1] - 1, RECT[2] + 1, RECT[3] + 1), 'districts/underground/old_convex_hulls.json')
print({r: len(v) for r, v in ROLE_IDS.items()})
print(len(props), 'props', len(district_lights), 'lights', len(panels), 'panels')
