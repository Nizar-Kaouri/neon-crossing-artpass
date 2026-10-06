"""PARK inventory from layout_dump.json (Claude, cloud). Run from art_pass/:
    python tools/convex_hulls.py -72 110 100 180 districts/park/old_convex_hulls.json
    python districts/park/make_inventory.py
Writes districts/park/PARK_INVENTORY.json (SHRINE_INVENTORY shape: no buildings, a `structures` role list + props).
The old park is FLAT: one ground slab (x -72..18, z 100..164, top y 0) inside the boundary walls (z 164, x 18).
Its furniture is in the dump under TWO names (check against districts/regions_map.png):
  - FullMapNativeRebuild / Step4Layout: 4 benches (3.2 x 0.8 m seat at 0.5 m, x -58 / -12, z 139 / 153) and 2 garden
    corners (2 m stone L-walls + a 0.9 m planter, x -60..-56 / -18..-14, z 149..154);
  - @Node3D@9344/Collision/MallStaticCollision (park pieces filed under the mall node): 8 tree trunks (0.5 x 0.5 x 2.8 m
    at x -69 / -57 / -13 / -1, z 137 / 157), 4 benches with backs (x -66 / -4, z 140 / 154), 4 raised planting beds on the
    lawns (6 x 2.5 x 1.17 m) and 2 shelters (counter 1.15 m, posts 2.6 m, roof 3.8 x 3 m at 2.6-2.75 m).
Routes (dump `routes`): N-S paths x -70 / -35 / 0 (3.8 m), cross paths z 146 (3.2 m) and z 160 (3.8 m). The tree trunks at
x -69 / -1 stand on the outer N-S paths in the old map; they stay exactly where they are (layout frozen).
Dressing (park painting style, old flat layout): materials by role (timber benches, stone walls / counters, planted
moss tops on the beds, tiled shelter roofs, timber trunks), pine crowns on the 8 old trunks (2 sakura accents), lantern
posts + bollard lamps placed only where they clear every collider and route corridor, shrubs beside the planters,
lawns + paved paths as flat patches (R2), a treeline on a lawn strip beyond the boundary walls as backdrop."""
import json, sys
import numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import SHAPES, S

RECTS = [[-72, 125, 2, 180], [2, 110, 100, 180]]
ROUTES_ALL = json.load(open('export/layout_dump.json'))['routes']


def clear_of_routes(x, z, r, clearance=0.6):
    """True if a disc (x, z, radius r) keeps `clearance` m away from every dump route corridor (full width)."""
    for rt in ROUTES_ALL:
        a = np.array([rt['from'][0], rt['from'][2]]); b = np.array([rt['to'][0], rt['to'][2]]); d = b - a
        t = np.clip(np.dot(np.array([x, z]) - a, d) / max(d @ d, 1e-9), 0, 1)
        if np.linalg.norm(np.array([x, z]) - a - t * d) < rt['width'] / 2 + r + clearance:
            return False
    return True
R = lambda v: round(float(v), 3)


def in_region(sh):
    cx, cz = (sh.lo[0] + sh.hi[0]) / 2, (sh.lo[2] + sh.hi[2]) / 2
    return any(r[0] <= cx < r[2] and r[1] <= cz < r[3] for r in RECTS) and sh.hi[1] >= -1.5


def role_of(s):
    p = s.s.get('path', '')
    sz = s.hi - s.lo
    cz = (s.lo[2] + s.hi[2]) / 2
    if 'Park west garden' in p or 'Park east garden' in p:
        return 'stone_low_wall'
    if p.startswith('FullMapNativeRebuild/Collision/'):
        if abs(sz[0] - 3.2) < 0.05 and abs(sz[1] - 0.2) < 0.05:
            return 'pavilion_post'                         # bench seat slab: timber (the old collider IS the bench)
        if sz[1] < 0.35 and sz[0] < 0.3 and s.hi[1] < 0.35:
            return 'bench_foot'                            # no role material: thin -> dark metal by size
    if 'MallStaticCollision' in p and s.t == 'box' and cz > 129.5:
        if abs(sz[0] - 0.5) < 0.01 and abs(sz[2] - 0.5) < 0.01 and sz[1] > 2:
            return 'tree_trunk'
        if abs(sz[0] - 3.0) < 0.05 and s.hi[1] < 1.3 and min(sz[0], sz[2]) > 0.1:
            return 'pavilion_post'                         # bench seat / back: timber
        if abs(sz[0] - 6.0) < 0.05 and abs(sz[1] - 1.05) < 0.02:
            return 'stone_low_wall'                        # planting bed body
        if abs(sz[0] - 5.6) < 0.05 and s.lo[1] > 1.0:
            return 'hill_surface'                          # planting bed top: moss + grass
        if abs(sz[0] - 3.8) < 0.05 and s.lo[1] > 2.5:
            return 'pavilion_roof'                         # shelter roof
        if abs(sz[0] - 3.4) < 0.05 and s.hi[1] < 1.2:
            return 'offering_table'                        # shelter counter: stone
        if sz[1] > 2.0 and min(sz[0], sz[2]) < 0.25:
            return 'pavilion_post'                         # shelter posts / back screen: timber
        if s.hi[1] < 0.45 and max(sz[0], sz[2]) < 0.7:
            return 'bench_foot'
    if s.t == 'box' and abs(s.hi[1]) < 0.01 and sz[0] > 1 and sz[2] > 20 and 'Mall' not in p:
        return 'ground'
    return None


shapes = [s for s in SHAPES if in_region(s)]
structures = []
for s in shapes:
    role = role_of(s)
    if role:
        structures.append({'dump_index': s.i, 'role': role, 'type': s.t, 'path': s.s.get('path', ''),
                           'aabb_min': [R(v) for v in s.lo], 'aabb_max': [R(v) for v in s.hi]})
SOLIDS = [s for s in shapes if s.hi[1] > 0.05 and (s.hi - s.lo)[1] < 30 and not (s.t != 'box')]


def clear_of_colliders(x, z, r, clearance=0.4):
    for s in SOLIDS:
        dx = max(s.lo[0] - x, 0, x - s.hi[0]); dz = max(s.lo[2] - z, 0, z - s.hi[2])
        if np.hypot(dx, dz) < r + clearance:
            return False
    return True


def free(x, z, r):
    return clear_of_routes(x, z, r) and clear_of_colliders(x, z, r)


ROUTES = [r for r in json.load(open('export/layout_dump.json'))['routes'] if str(r.get('kind', '')).startswith('Park')]
props, lights = [], []

# Crowns on the 8 old trunk colliders (crowns start at 2.4 m: above head height even over the path corridors).
for k, st in enumerate(s for s in structures if s['role'] == 'tree_trunk'):
    lo, hi = st['aabb_min'], st['aabb_max']
    x, z = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    props += [{'piece': 'F_sakura_cloud' if k in (2, 5) else 'F_pine_cloud', 'pos': [R(x), 2.4, R(z)], 'rot': float(k * 47 % 360), 'for': st['dump_index']},
              {'piece': 'F_pine_cloud', 'pos': [R(x + 0.45), 2.95, R(z - 0.35)], 'rot': float(k * 71 % 360), 'for': st['dump_index']},
              {'piece': 'F_pine_cloud', 'pos': [R(x - 0.4), 3.3, R(z + 0.3)], 'rot': float(k * 29 % 360), 'for': st['dump_index']}]

# Lantern posts: one beside each bench, plus the two ends of the central path; first candidate that clears every
# collider (0.4 m) and route corridor (0.6 m) wins. Bollard lamps at the outer lawn corners, same rule.
def lamp(cands, piece='P_lamp_lantern_post', head=2.4, r=0.19):
    for x, z in cands:
        if free(x, z, r):
            props.append({'piece': piece, 'pos': [R(x), 0.0, R(z)], 'rot': 0.0})
            if head:
                lights.append({'path': 'park/%s' % piece, 'class': 'OmniLight3D', 'position': [R(x), head, R(z)]})
            return True
    return False


placed_lamps = 0
for st in structures:
    lo, hi = st['aabb_min'], st['aabb_max']
    if st['role'] == 'pavilion_post' and abs(hi[0] - lo[0] - 3.2) < 0.05:
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        out = -1 if cx < -35 else 1
        placed_lamps += lamp([(cx + out * 2.2, cz), (cx + out * 2.2, cz - 1.0), (cx - out * 2.2, cz), (cx, cz - 1.2), (cx, cz + 1.2)])
for x in (-37.8, -32.2):
    for z in (137.2, 156.5):
        placed_lamps += lamp([(x, z)])
for x, z in ((-51.3, 137.3), (-51.3, 156.4), (-18.5, 137.3), (-18.5, 156.4)):
    lamp([(x, z)], 'P_bollard_lamp', 0.0, 0.1)
# Shrubs: beside the two planters and the four planting beds (on the lawn / ground, never on a top).
for st in structures:
    lo, hi = st['aabb_min'], st['aabb_max']
    if st['path'].endswith('Planter') or (st['role'] == 'stone_low_wall' and abs(hi[0] - lo[0] - 6.0) < 0.05):
        for x, z in ((lo[0] - 1.0, lo[2] + 0.3), (hi[0] + 1.0, hi[2] - 0.3), (lo[0] - 1.0, hi[2] - 0.3), (hi[0] + 1.0, lo[2] + 0.3)):
            if free(x, z, 0.45):
                props.append({'piece': 'F_shrub' if (int(x) + int(z)) % 2 else 'F_shrub_small', 'pos': [R(x), 0.0, R(z)], 'rot': float(int(x * 13 + z) % 360)})


def tree(x, z, k, crown='F_pine_cloud'):
    props.append({'piece': 'P_tree_trunk_pine', 'pos': [R(x), 0.0, R(z)], 'rot': float(k * 37 % 360)})
    props.append({'piece': crown, 'pos': [R(x), 2.45, R(z)], 'rot': float(k * 47 % 360)})
    props.append({'piece': 'F_pine_cloud', 'pos': [R(x + 0.45), 2.95, R(z - 0.35)], 'rot': float(k * 71 % 360)})


patches = [
    {'rect_xz': [-50.9, 137.7, -37.0, 156.0], 'top_y': 0.012, 'mat': 'lawn', 'note': 'west lawn (old map)'},
    {'rect_xz': [-33.1, 137.7, -18.9, 156.0], 'top_y': 0.012, 'mat': 'lawn', 'note': 'east lawn (old map)'},
    {'rect_xz': [-36.9, 130.0, -33.1, 162.0], 'top_y': 0.01, 'mat': 'paving', 'note': 'central path x -35 (route)'},
    {'rect_xz': [-71.9, 130.0, -68.1, 162.0], 'top_y': 0.01, 'mat': 'paving', 'note': 'west path x -70 (route)'},
    {'rect_xz': [-1.9, 130.0, 1.9, 162.0], 'top_y': 0.01, 'mat': 'paving', 'note': 'east path x 0 (route)'},
    {'rect_xz': [-68.1, 158.1, -1.9, 161.9], 'top_y': 0.01, 'mat': 'paving', 'note': 'south cross path z 160 (route)'},
    {'rect_xz': [-68.1, 144.4, -50.9, 147.6], 'top_y': 0.01, 'mat': 'paving', 'note': 'middle cross path z 146, west part'},
    {'rect_xz': [-18.9, 144.4, -1.9, 147.6], 'top_y': 0.01, 'mat': 'paving', 'note': 'middle cross path z 146, east part'},
    {'rect_xz': [-72.0, 164.3, 26.0, 176.0], 'top_y': 0.0, 'thick': 0.6, 'mat': 'lawn', 'note': 'backdrop south (outside boundary z 164)'},
    {'rect_xz': [18.3, 100.0, 26.0, 164.3], 'top_y': 0.0, 'thick': 0.6, 'mat': 'lawn', 'note': 'backdrop east (outside boundary x 18)'},
]
# Backdrop treeline beyond the boundary walls (never reachable: invisible wall 55 m tall at z 164 / x 18).
for k, x in enumerate(range(-70, 24, 7)):
    z = 166.5 + (k % 2) * 2.6
    tree(x, z, k + 10, 'F_sakura_cloud' if k % 4 == 1 else 'F_pine_cloud')
for k, z in enumerate(range(104, 162, 8)):
    tree(20.5 + (k % 2) * 2.4, z, k + 30)

inv = {'schema_version': 1, 'district': 'park', 'source': 'layout_dump.json + regions_map.png (Claude, cloud)',
       'region': {'rects': RECTS}, 'buildings': [], 'structures': structures, 'routes': ROUTES,
       'props': props, 'lights_in_or_affecting_region': lights, 'ground_patches': patches,
       'summary': 'Flat park, no buildings. Ground slab top y 0 (x -72..18, z 100..164), boundary walls z 164 / x 18. '
                  '8 benches (x -58 / -12 at z 139 / 153; with backs x -66 / -4 at z 140 / 154), 2 garden corners (2 m stone '
                  'L-walls + 0.9 m planter), 2 shelters (x -59.7..-56.3 / -13.7..-10.3, z 149.5..152.5, roof 2.6-2.75 m), '
                  '4 raised planting beds on the lawns (1.17 m), 8 tree trunks (2.8 m). Routes: N-S paths x -70 / -35 / 0 '
                  '(3.8 m), cross paths z 146 (3.2 m) and z 160 (3.8 m). Lawns had no collision.',
       'dressing_plan': 'Park painting style on the old flat layout: lawns + paved paths as 1 cm patches, pines with layered '
                        'crowns (2 sakura accents), wooden benches on the old bench colliders, lantern posts + bollard lamps '
                        '(baked light), shrubs on the planters and lawn corners, treeline backdrop outside the boundary.'}
json.dump(inv, open('districts/park/PARK_INVENTORY.json', 'w'), indent=1)
print(placed_lamps, 'lantern posts;', len(structures), 'structures', {r: sum(1 for s in structures if s['role'] == r) for r in set(s['role'] for s in structures)},
      len(props), 'props', len(lights), 'lights', len(patches), 'patches')

# old_convex_hulls.json: tools/convex_hulls.py -72 110 100 180 returns only the MALL's convex shell pieces (758 hulls,
# 2 300 draw calls when drawn here). The mall district dresses them; the park keeps none of them.
H = 'districts/park/old_convex_hulls.json'
try:
    hulls = json.load(open(H))
    keep = {k: v for k, v in hulls.items() if 'Mall' not in S[int(k)].get('path', '')}
    json.dump(keep, open(H, 'w'))
    print('hulls kept', len(keep), 'of', len(hulls))
except FileNotFoundError:
    print('run tools/convex_hulls.py -72 110 100 180', H, 'first')
