"""Self-check for a district (Claude, cloud). Run from the project root (the folder with project.godot):
  python art_pass/districts/station/selfcheck.py <district> [builder_scene.tscn]
1) writes the safety volumes, 2) runs selfcheck_dump.gd (Godot builds the scene and samples every visual triangle near
a volume), 3) tests the points:
  - doorways: nothing visual inside the opening from sill + 2 cm to sill + 2.05 m (whole wall thickness + 30 cm each side)
  - stair flights: nothing from the ramp surface + 10 cm (the drawn treads straddle the ramp by <= 9 cm) to + 2 m
  - stair landings: nothing from the landing top + 2 cm to + 2 m
  Points lying on an old collider surface (merged meshes also hold the rebuilt old boxes) are not new visuals: ignored.
4) checks every inventory prop: >= 2.05 m above the floor below it, or flush on the floor (tactile), or on a wall.
Writes art_pass/districts/<district>/selfcheck_result.json and prints a summary."""
import sys, os, json, subprocess, numpy as np
os.chdir('art_pass')
sys.path.insert(0, 'districts/station')
from dresslib import BY_I, solid_at, SHAPES     # noqa: E402

d = sys.argv[1]
scene = sys.argv[2] if len(sys.argv) > 2 else 'res://art_pass/districts/%s/%s.tscn' % (d, d)
inv = json.load(open('districts/%s/%s_INVENTORY.json' % (d, d.upper())))
vols = []
for b in inv.get('buildings', []):
    for side in b['street_facing_sides']:
        n = side['normal_xz']
        for o in side['openings']:
            c = o['centre_xyz']; hw = o['width_m'] / 2 - 0.02; y0 = o.get('sill_y', 0.0) + 0.02
            if n[1] != 0:
                lo, hi = [c[0] - hw, y0, c[2] - 0.5], [c[0] + hw, o.get('sill_y', 0.0) + 2.05, c[2] + 0.5]
            else:
                lo, hi = [c[0] - 0.5, y0, c[2] - hw], [c[0] + 0.5, o.get('sill_y', 0.0) + 2.05, c[2] + hw]
            vols.append({'kind': 'doorway', 'name': '%s %s' % (b['id'], n), 'lo': lo, 'hi': hi})
for o in inv.get('openings', []):
    lo, hi = [list(v) for v in o['box']]
    for k in (0, 2):
        if hi[k] - lo[k] > 0.1:
            lo[k] += 0.02; hi[k] -= 0.02
    lo[1] += 0.02
    vols.append({'kind': 'doorway', 'name': o['name'], 'lo': lo, 'hi': hi})
stairs = [s for s in inv['structures'] if s['role'] in ('stair_flight', 'stair_flight_ramp')]
landings = [s for s in inv['structures'] if s['role'] == 'stair_landing']
for s in stairs + landings:
    vols.append({'kind': 'stair_landing' if s['role'] == 'stair_landing' else 'stair_flight', 'name': str(s['dump_index']), 'lo': s['aabb_min'], 'hi': [s['aabb_max'][0], s['aabb_max'][1] + 2.0, s['aabb_max'][2]]})
json.dump(vols, open('/tmp/selfcheck_vols_%s.json' % d, 'w'))

pts_file = '/tmp/selfcheck_pts_%s.json' % d
r = subprocess.run(['godot', '--headless', '--path', '..', '-s', 'res://art_pass/districts/station/selfcheck_dump.gd', '--',
                    '--scene=' + scene, '--vols=/tmp/selfcheck_vols_%s.json' % d, '--out=' + pts_file], capture_output=True, text=True)
print([l for l in r.stdout.splitlines() if 'SELFCHECK' in l or 'DISTRICT' in l or 'SCRIPT ERROR' in l])
dump = json.load(open(pts_file))


def in_stair(P, s):
    ax = s['axis']; n = s['plane']
    o = np.array(ax['origin_xz']); dv = np.array(ax['dir_xz']); pv = np.array([-dv[1], dv[0]])
    rel = P[:, [0, 2]] - o
    along, across = rel @ dv, rel @ pv - ax['mid_across']
    surf = -(n[0] * P[:, 0] + n[2] * P[:, 2] + n[3]) / n[1]
    return (np.abs(across) < s['width_true'] / 2 - 0.02) & (along > ax['along_min'] + 0.02) & (along < ax['along_max'] - 0.02) & \
           (P[:, 1] > surf + 0.10) & (P[:, 1] < surf + 2.0)


def on_footprint(P, s):
    ax = s['axis']
    o = np.array(ax['origin_xz']); dv = np.array(ax['dir_xz']); pv = np.array([-dv[1], dv[0]])
    rel = P[:, [0, 2]] - o
    along, across = rel @ dv, rel @ pv - ax['mid_across']
    return (np.abs(across) <= s['width_true'] / 2) & (along >= ax['along_min']) & (along <= ax['along_max'])


def in_landing(P, s):
    sh = BY_I[s['dump_index']]
    m = np.zeros(len(P), bool)
    for h in np.arange(0.02, 2.0, 0.05):
        m |= sh.inside(P - np.array([0, h, 0]), -0.02)
    return m


fails = {}
skyline = set()
for m in dump:
    P = np.array(m['pts']).reshape(-1, 3)
    for v in vols:
        lo, hi = np.array(v['lo']), np.array(v['hi'])
        sel = P[np.all((P >= lo - 0.01) & (P <= hi + 0.01), axis=1)]
        if not len(sel):
            continue
        if v['kind'] == 'doorway':
            hit = sel[np.all((sel > lo) & (sel < hi), axis=1)]
        elif v['kind'] == 'stair_flight':
            hit = sel[in_stair(sel, next(s for s in stairs if str(s['dump_index']) == v['name']))]
        else:
            hit = sel[in_landing(sel, next(s for s in landings if str(s['dump_index']) == v['name']))]
            on_flight = np.zeros(len(hit), bool)             # where a flight overlaps its landing, the flight rule decides
            for s in stairs:
                on_flight |= on_footprint(hit, s)
            hit = hit[~on_flight]
        if len(hit):
            hit = hit[~solid_at(hit, 0.01)]                 # on an old collider surface = the old map itself
        if len(hit) and m['mesh'].startswith('MergedQuads') and np.ptp(P[:, 0]) > 100:
            skyline.add(m['mesh'])                       # the shared far skyline cards (see BUILDER_REQUESTS R5)
            continue
        if len(hit):
            k = '%s %s' % (v['kind'], v['name'])
            fails.setdefault(k, []).append({'mesh': m['mesh'], 'n': int(len(hit)), 'example': np.round(hit[0], 3).tolist()})

# props: clearance above the floor below them
nonc = [s for s in SHAPES if s.t != 'concave']
props = {'ok_high': 0, 'ok_wall': 0, 'ok_flush': 0, 'floor_prop': []}
for p in inv.get('props', []):
    if 'aabb' not in p:
        continue
    lo, hi = np.array(p['aabb'][0]), np.array(p['aabb'][1])
    c = (lo + hi) / 2
    ys = np.arange(min(hi[1] - 0.001, lo[1] + 0.11), lo[1] - 6.0, -0.02)
    col = solid_at(np.stack([np.full(len(ys), c[0]), ys, np.full(len(ys), c[2])], 1), shapes=[s for s in nonc if s.lo[0] <= c[0] <= s.hi[0] and s.lo[2] <= c[2] <= s.hi[2]])
    floor = ys[np.argmax(col)] if col.any() else -99
    wall = False
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q = c + np.array([dx, 0, dz]) * ((hi - lo)[0 if dx else 2] / 2 + 0.12)
        if solid_at(q)[0]:
            wall = True
    if lo[1] - floor >= 2.05:
        props['ok_high'] += 1
    elif hi[1] - floor <= 0.03:
        props['ok_flush'] += 1
    elif wall:
        props['ok_wall'] += 1
    else:
        props['floor_prop'].append({'piece': p['piece'], 'pos': p['pos'], 'clear_m': round(float(lo[1] - floor), 2), 'why': p.get('why', '')})
res = {'district': d, 'scene': scene, 'volumes': {k: sum(1 for v in vols if v['kind'] == k) for k in ('doorway', 'stair_flight', 'stair_landing')},
       'meshes_sampled': len(dump), 'intrusions': fails, 'skyline_cards_crossing_volumes': sorted(skyline), 'props': props}
json.dump(res, open('districts/%s/selfcheck_result%s.json' % (d, '' if len(sys.argv) < 3 else '_preview'), 'w'), indent=1)
print('volumes', res['volumes'], 'meshes sampled', len(dump))
print('skyline cards crossing volumes (shared builder, R5):', sorted(skyline))
print('INTRUSIONS:', 'none' if not fails else json.dumps(fails, indent=1))
print('props: high %d, wall %d, flush %d, floor props %d' % (props['ok_high'], props['ok_wall'], props['ok_flush'], len(props['floor_prop'])))
for f in props['floor_prop']:
    print('  floor prop', f)
