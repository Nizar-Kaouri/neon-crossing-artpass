"""HOMES inventory from layout_dump.json (Claude, cloud). Run from art_pass/:
    python districts/homes/make_inventory.py
Writes districts/homes/HOMES_INVENTORY.json in the ALLEY_INVENTORY / SHRINE_INVENTORY shape the shared builder reads:
- buildings: one entry per house body and one per garden wing (the old FullMapNativeRebuild names A1..A3, V1..V7).
  None can be entered: no ground-floor openings (checked: the dump has no doorway gaps in any of them).
  The roofs, balconies, sun terraces, fold landings and service flights are ROUTES -> `roof_is_route: true`.
- structures: dump index -> role (materials by role: stone garden edges / screen, timber planter beds, tree trunk).
- props: tree crowns on the old trunk collider, lantern posts on the old 2.3 m post colliders, shrubs inside the
  garden plots (never on a route corridor, a ramp or a roof - see self_check.py), backdrop trees beyond the boundary.
- lights_in_or_affecting_region: lamp heads (baked lights, read by the builder's _street()).
- ground_patches: flat lawn plots (BUILDER_REQUESTS R2; ignored by the current builder).
inventory.py (slab clusters) was run first (see REPORT.md); it splits the houses the same way but cannot name them."""
import json, re, sys
import numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import SHAPES

RECTS = [[31, 2, 100, 110], [2, 30, 31, 110]]
ROUTES_ALL = json.load(open('export/layout_dump.json'))['routes']


def clear_of_routes(x, z, r, clearance=0.6):
    """True if a disc (x, z, radius r) keeps `clearance` m away from every dump route corridor (full width)."""
    for rt in ROUTES_ALL:
        a = np.array([rt['from'][0], rt['from'][2]]); b = np.array([rt['to'][0], rt['to'][2]]); d = b - a
        t = np.clip(np.dot(np.array([x, z]) - a, d) / max(d @ d, 1e-9), 0, 1)
        if np.linalg.norm(np.array([x, z]) - a - t * d) < rt['width'] / 2 + r + clearance:
            return False
    return True


def in_region(sh):
    cx, cz = (sh.lo[0] + sh.hi[0]) / 2, (sh.lo[2] + sh.hi[2]) / 2
    return any(r[0] <= cx < r[2] and r[1] <= cz < r[3] for r in RECTS) and sh.hi[1] >= -1.5


R = lambda v: round(float(v), 3)
shapes = [s for s in SHAPES if in_region(s)]
named = {}
for s in shapes:
    m = re.match(r'FullMapNativeRebuild/Collision/([AV]\d)(\w+)$', s.s.get('path', ''))
    if m:
        named.setdefault(m.group(1), {})[m.group(2)] = s


def top(s):
    return R(s.hi[1])


def plain_faces(hid, b):
    """R4: faces whose 0.19 m window frames would reach into a service-flight corridor of this house (gap < 0.2 m)."""
    out = []
    for rt in ROUTES_ALL:
        if not str(rt['kind']).startswith(hid + 'ServiceFlight'):
            continue
        x, w = rt['from'][0], rt['width']
        z0, z1 = sorted((rt['from'][2], rt['to'][2]))
        if z1 < b.lo[2] or z0 > b.hi[2]:
            continue
        if 0 <= b.lo[0] - (x + w / 2) < 0.2 and [-1, 0] not in out:
            out.append([-1, 0])
    return out


buildings, structures, routes_tops = [], [], []
for hid in sorted(named):
    parts = named[hid]
    for key, suffix, kind in (('Body', '', 'apartment_block' if hid[0] == 'A' else 'house'), ('GardenWingBody', 'w', 'house_wing')):
        if key not in parts:
            continue
        b = parts[key]
        roof = parts.get('Roof' if key == 'Body' else 'GardenWingRoof')
        sides = [{'normal_xz': n, 'street': True, 'wall_cover': 1.0, 'openings': []} for n in ([0, 1], [0, -1], [1, 0], [-1, 0])]
        buildings.append({'id': hid + suffix, 'kind': kind, 'name': '%s %s' % (hid, 'garden wing' if suffix else 'house'),
                          'footprint': {'centre_xz': [R((b.lo[0] + b.hi[0]) / 2), R((b.lo[2] + b.hi[2]) / 2)],
                                        'width_m': R(b.hi[0] - b.lo[0]), 'depth_m': R(b.hi[2] - b.lo[2])},
                          'roof': {'roof_y': top(roof) if roof else top(b), 'can_players_stand': 'yes (route)'},
                          'roof_is_route': True, 'enterable': False, 'cornice_depth': 0.11 if plain_faces(hid, b) else 0.12, 'plain_faces': plain_faces(hid, b),
                          'street_facing_sides': sides, 'dump_shapes': [b.i] + ([roof.i] if roof else [])})
    for k, s in sorted(parts.items()):
        if any(t in k for t in ('Roof', 'Terrace', 'LandingDeck', 'RoofThreshold')):
            routes_tops.append({'house': hid, 'part': k, 'dump_index': s.i, 'top_y': top(s),
                                'rect_xz': [R(s.lo[0]), R(s.lo[2]), R(s.hi[0]), R(s.hi[2])]})

ROLE_BY_PATH = [('GardenEdge', 'stone_low_wall'), ('courtyard screen', 'stone_low_wall')]
for s in shapes:
    p = s.s.get('path', '')
    role = next((r for k, r in ROLE_BY_PATH if k in p), None)
    sz = s.hi - s.lo
    if role is None and 'FullMapNativeRebuild/Collision/@StaticBody3D' in p and s.t == 'box' and s.lo[1] < 0.05 and abs(s.hi[1] - 0.6) < 0.05 and min(sz[0], sz[2]) < 0.4:
        role = 'stone_low_wall'                                  # unnamed east garden edges (0.6 m kerbs)
    if p.startswith('ResidentialDistrict/'):
        if s.t == 'cylinder' and sz[1] > 4:
            role = 'tree_trunk'
        elif s.t == 'cylinder':
            role = 'lamp_post'                                   # 2.3 m posts: no role material, lantern post placed on them
        else:
            role = 'pavilion_post'                               # 2.6 x 2 x 0.6 raised planter beds: timber edging
    if role:
        structures.append({'dump_index': s.i, 'role': role, 'type': s.t, 'path': p,
                           'aabb_min': [R(v) for v in s.lo], 'aabb_max': [R(v) for v in s.hi]})

props, lights = [], []
for st in structures:
    lo, hi = st['aabb_min'], st['aabb_max']
    cx, cz = R((lo[0] + hi[0]) / 2), R((lo[2] + hi[2]) / 2)
    if st['role'] == 'tree_trunk':                               # crown on top of the old trunk (above 4 m)
        props += [{'piece': 'F_pine_cloud', 'pos': [cx, R(hi[1] - 0.6), cz], 'rot': 0.0},
                  {'piece': 'F_pine_cloud', 'pos': [R(cx + 0.5), R(hi[1] - 0.2), R(cz - 0.3)], 'rot': 40.0},
                  {'piece': 'F_sakura_cloud', 'pos': [R(cx - 0.4), R(hi[1] - 0.9), R(cz + 0.4)], 'rot': 10.0}]
    if st['role'] == 'lamp_post':                                # lantern post exactly on the old post collider
        props.append({'piece': 'P_lamp_lantern_post', 'pos': [cx, 0.0, cz], 'rot': 0.0})
        lights.append({'path': 'homes/lamp_%d' % st['dump_index'], 'class': 'OmniLight3D', 'position': [cx, 2.45, cz]})

# Garden plots: the area between a house's two 0.6 m garden kerbs (old map: flat lawn, no collision).
PLOTS = {'A1': [2.3, 23.0, 19.3, 40.0], 'A2': [2.3, 54.0, 19.3, 70.0], 'A3': [23.3, 23.0, 50.3, 48.0], 'V1': [23.3, 54.0, 38.3, 70.0],
         'V2': [42.3, 78.0, 60.3, 97.0], 'V3': [64.3, 78.0, 87.3, 97.0], 'V4': [64.3, 23.0, 87.3, 43.0], 'V5': [64.3, 49.0, 87.3, 71.0],
         'V6': [2.3, 78.0, 19.3, 97.0], 'V7': [23.3, 78.0, 41.3, 97.0]}
patches = [{'rect_xz': r, 'top_y': 0.012, 'mat': 'lawn', 'note': hid + ' garden plot'} for hid, r in PLOTS.items()]
patches.append({'rect_xz': [42.5, 54.0, 57.5, 68.0], 'top_y': 0.012, 'mat': 'lawn', 'note': 'residential green (tree, beds, lamps)'})
# Shrubs in the plot corners on the far side from the service flights (east side of each house, south-east corner).
for hid, r in PLOTS.items():
    for (x, z) in ((r[2] - 0.9, r[3] - 0.9), (r[2] - 0.9, r[1] + 0.9)):
        if not clear_of_routes(x, z, 0.5):
            continue                                             # plot corner on a residential walk: no shrub
        props.append({'piece': 'F_shrub', 'pos': [R(x), 0.0, R(z)], 'rot': float((int(x * 7 + z * 3)) % 360)})
# Backdrop beyond the boundary walls (x 92, z 100): lawn strip + trees, never reachable.
patches += [{'rect_xz': [92.3, 2.0, 104.0, 112.0], 'top_y': 0.0, 'thick': 0.6, 'mat': 'lawn', 'note': 'backdrop east (outside boundary)'},
            {'rect_xz': [17.0, 100.3, 104.0, 112.0], 'top_y': 0.0, 'thick': 0.6, 'mat': 'lawn', 'note': 'backdrop south (outside boundary)'}]
for k, z in enumerate(range(8, 100, 9)):
    x = 94.5 + (k % 2) * 2.5
    props += [{'piece': 'P_tree_trunk_pine', 'pos': [x, 0.0, float(z)], 'rot': float(k * 37 % 360)},
              {'piece': 'F_pine_cloud', 'pos': [x, 2.5, float(z)], 'rot': float(k * 53 % 360)}]
for k, x in enumerate(range(22, 92, 9)):
    z = 102.5 + (k % 2) * 2.5
    props += [{'piece': 'P_tree_trunk_pine', 'pos': [float(x), 0.0, z], 'rot': float(k * 41 % 360)},
              {'piece': 'F_pine_cloud' if k % 3 else 'F_sakura_cloud', 'pos': [float(x), 2.5, z], 'rot': float(k * 29 % 360)}]

inv = {'schema_version': 1, 'district': 'homes', 'source': 'layout_dump.json (Claude, cloud): named FullMapNativeRebuild houses A1-A3, V1-V7',
       'region': {'rects': RECTS}, 'buildings': buildings, 'structures': structures, 'route_tops': routes_tops,
       'props': props, 'lights_in_or_affecting_region': lights, 'ground_patches': patches,
       'summary': '10 houses that cannot be entered (3 apartment blocks A1-A3 with 4-5 storey service flights, 7 villas V1-V7 '
                  'with a garden wing). Routes: the outdoor service flights (zig-zag ramps on the west side), fold landings, '
                  'balcony terraces, sun terraces, garden-wing roofs, roof thresholds and the main roofs. Each house sits in a '
                  'flat garden plot bounded by 0.6 m kerbs. Residential green at x 42-58, z 54-68: one tree trunk, two lamp '
                  'posts, two raised beds.',
       'dressing_plan': 'Cladding + windows + cornice from the shared builder (kinds apartment_block/house/house_wing: plain, not '
                        'traditional - no eaves, noren, porch posts or ivy over the balconies and flights; cornice 12 cm, R3). Nothing on any roof, balcony, terrace, landing or '
                        'flight (roof antenna off via roof_is_route, R1). Lawns as flat patches (R2). Stone kerbs, crowns on the '
                        'old trunk, lantern posts on the old posts, shrubs in plot corners, backdrop trees outside the boundary.'}
json.dump(inv, open('districts/homes/HOMES_INVENTORY.json', 'w'), indent=1)
print(len(buildings), 'buildings', len(structures), 'structures', len(props), 'props', len(lights), 'lights', len(patches), 'patches', len(routes_tops), 'route tops')
for b in buildings:
    print(b['id'], b['kind'], b['footprint'], b['roof'])
