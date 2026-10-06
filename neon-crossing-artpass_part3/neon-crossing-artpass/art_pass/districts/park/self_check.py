"""District self-check (Claude, cloud): no visual mesh in an opening, a route corridor, a stair/ramp volume or on a
walkable top (roof, balcony, terrace, landing, threshold, wall cap...). Run from art_pass/ after dump_tris.gd:
    python districts/<homes|park>/self_check.py <homes|park> <tris prefix>   ->  districts/<d>/SELF_CHECK.json + printed table
Method: every visual triangle of the BUILT scene (after merging) is sampled every 8 cm. A sample is an INTRUSION when it
lies in a forbidden volume and is not part of / flush against an old collider:
  - route corridors: every dump `routes` segment touching the district (paths, lanes, the service flights), full
    width, from the route surface +3 cm to +2.05 m (flights: the sloped line from->to);
  - walkable tops: the top face of every old box collider >= 0.75 x 0.75 m above y 0.3 (roofs, balconies, terraces,
    landings, thresholds, planters, bench seats, shelter roofs; not 0.5 m tree trunks or 0.4 m wall caps), from top +3 cm
    to top +2.0 m;
  - openings: inventory street_facing_sides[].openings, < 2.05 m (homes: none, the houses cannot be entered).
  Wall skin exemption: a sample within 0.2 m of an old collider that rises at least to the sample's height (cladding,
  window frames, cornices on a wall) is flush dressing, not an obstacle; inside a stair / flight volume only 0.12 m
  (the builder's cladding: 5 cm gap + 6 cm board). The floor under a sample never exempts it.
Old collider visuals are exempt by construction (they ARE the colliders). Samples on the old ground slab (top y 0) outside
every route corridor are listed as DRESSING (trees, lamps, shrubs) - allowed, but listed so they can be reviewed.
Backdrop beyond the boundary walls (no ground slab, unreachable) is not checked."""
import json, sys
import numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import SHAPES

D = sys.argv[1]
tris = np.fromfile(sys.argv[2] + '.bin', dtype='<f4').reshape(-1, 3, 3).astype(np.float64)
index = json.load(open(sys.argv[2] + '.json'))
inv = json.load(open('districts/%s/%s_INVENTORY.json' % (D, D.upper())))
dump = json.load(open('export/layout_dump.json'))
RECTS = inv['region']['rects']
bx0 = min(r[0] for r in RECTS) - 2; bz0 = min(r[1] for r in RECTS) - 2; bx1 = max(r[2] for r in RECTS) + 2; bz1 = max(r[3] for r in RECTS) + 2
in_rects = lambda x, z: np.any([(x >= r[0]) & (x < r[2]) & (z >= r[1]) & (z < r[3]) for r in RECTS], axis=0)

names = np.empty(len(tris), dtype=object)
for name, a, b in index:
    names[a:b] = name
keep = np.array([not ('Skyline' in str(n)) for n in names])
near = [s for s in SHAPES if s.hi[0] > bx0 - 5 and s.lo[0] < bx1 + 5 and s.hi[2] > bz0 - 5 and s.lo[2] < bz1 + 5 and (s.hi - s.lo)[1] < 30]

# ---- forbidden volumes
routes = []
for r in dump['routes']:
    a, b = np.array(r['from'], float), np.array(r['to'], float)
    if not (in_rects(np.array([a[0], b[0]]), np.array([a[2], b[2]])).any()):
        continue
    if a[1] <= 0.13 and b[1] <= 0.13:
        a[1] = b[1] = 0.0
    routes.append((str(r['kind']), a, b, float(r['width'])))
tops = []
for s in near:
    if s.t != 'box':
        continue
    B = np.abs(s.B)
    if not (np.allclose(B, np.eye(3), atol=1e-3) or np.allclose(B, [[0, 0, 1], [0, 1, 0], [1, 0, 0]], atol=1e-3)):
        continue
    cx, cz = (s.lo[0] + s.hi[0]) / 2, (s.lo[2] + s.hi[2]) / 2
    if not in_rects(np.array([cx]), np.array([cz]))[0]:
        continue
    if s.hi[1] > 0.3 and s.hi[0] - s.lo[0] >= 0.75 and s.hi[2] - s.lo[2] >= 0.75:
        tops.append((s.s.get('path', '').split('/')[-1], s.lo[[0, 2]], s.hi[[0, 2]], float(s.hi[1])))
ground_slabs = [(s.lo[[0, 2]], s.hi[[0, 2]]) for s in near if s.t == 'box' and abs(s.hi[1]) < 0.02 and (s.hi[0] - s.lo[0]) * (s.hi[2] - s.lo[2]) > 20]
openings = []
for b in inv.get('buildings', []):
    for side in b.get('street_facing_sides', []):
        openings += side.get('openings', [])


def samples(T, step=0.08):
    a, b, c = T
    L = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b))
    if L > 3.0:
        step = 0.2                                   # big faces (merged cladding, slabs): 20 cm is enough to catch a crossing
    n = min(int(L / step) + 1, 300)
    i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
    m = i + j <= n
    u, v = i[m] / n, j[m] / n
    return a + np.outer(u, b - a) + np.outer(v, c - a)


def wall_skin(P, pad=0.2):
    """True where a sample sits within 0.2 m of an old collider that rises at least to the sample's height."""
    ok = np.zeros(len(P), bool)
    cell = 8.0
    keys = np.floor(P[:, [0, 2]] / cell).astype(int)
    order = np.lexsort((keys[:, 1], keys[:, 0]))
    ks = keys[order]
    brk = np.nonzero(np.any(np.diff(ks, axis=0) != 0, axis=1))[0] + 1
    for grp in np.split(order, brk):
        if len(grp) == 0:
            continue
        Q = P[grp]
        qlo, qhi = Q.min(0) - pad, Q.max(0) + pad
        r = np.zeros(len(Q), bool)
        for s in near:
            if s.hi[0] < qlo[0] or s.lo[0] > qhi[0] or s.hi[2] < qlo[2] or s.lo[2] > qhi[2] or s.hi[1] < qlo[1] + pad - 0.01:
                continue
            cand = (~r) & (Q[:, 1] <= s.hi[1] + 0.01)
            if cand.any():
                r[cand] |= s.inside(Q[cand], pad)
        ok[grp] = r
    return ok


def classify(P):
    """Per sample: 0 free, 1 ground route, 5 stair/flight route, 2 walkable top, 3 opening, 4 open ground (dressing)."""
    cls = np.zeros(len(P), int)
    for kind, a, b, w in routes:
        d = (b - a)[[0, 2]]; L2 = max(d @ d, 1e-9)
        rel = P[:, [0, 2]] - a[[0, 2]]
        t = np.clip(rel @ d / L2, 0, 1)
        lat = np.linalg.norm(rel - np.outer(t, d), axis=1)
        floor = a[1] + t * (b[1] - a[1])
        h = P[:, 1] - floor
        cls[(lat <= w / 2) & (h > 0.03) & (h < 2.05) & (cls == 0)] = 5 if abs(b[1] - a[1]) > 0.5 else 1
    for name, lo, hi, y in tops:
        m = (P[:, 0] >= lo[0]) & (P[:, 0] <= hi[0]) & (P[:, 2] >= lo[1]) & (P[:, 2] <= hi[1]) & (P[:, 1] > y + 0.03) & (P[:, 1] < y + 2.0)
        cls[m & (cls == 0)] = 2
    for o in openings:
        c = np.array(o['centre_xyz']); hw = o['width_m'] / 2
        m = (np.abs(P[:, 0] - c[0]) <= hw) & (np.abs(P[:, 2] - c[2]) <= 0.6) & (P[:, 1] < 2.05)
        cls[m] = 3
    g = (cls == 0) & (P[:, 1] > 0.03) & (P[:, 1] < 2.05) & in_rects(P[:, 0], P[:, 2])
    on_slab = np.zeros(len(P), bool)                  # open ground = above the old ground slab (backdrop beyond the
    for lo, hi in ground_slabs:                       # boundary walls is unreachable and not listed)
        on_slab |= (P[:, 0] >= lo[0]) & (P[:, 0] <= hi[0]) & (P[:, 2] >= lo[1]) & (P[:, 2] <= hi[1])
    g &= on_slab
    cls[g] = 4
    return cls


lo_all = np.array([bx0, -1.0, bz0]); hi_all = np.array([bx1, 60.0, bz1])
tlo, thi = tris.min(1), tris.max(1)
cand = keep & np.all(thi >= lo_all, 1) & np.all(tlo <= hi_all, 1)
# volume AABBs: a triangle is sampled only if its AABB touches one of them (or the open ground below 2.05 m)
vols = []
for kind, a, b, w in routes:
    vols.append((np.minimum(a, b) - [w / 2, 0, w / 2], np.maximum(a, b) + [w / 2, 2.05, w / 2]))
for name, lo, hi, y in tops:
    vols.append((np.array([lo[0], y, lo[1]]), np.array([hi[0], y + 2.0, hi[1]])))
for o in openings:
    c = np.array(o['centre_xyz']); vols.append((c - [o['width_m'] / 2, c[1], 0.6], c + [o['width_m'] / 2, 2.05, 0.6]))
vlo = np.array([v[0] for v in vols]); vhi = np.array([v[1] for v in vols])
ground = (tlo[:, 1] < 2.05) & (thi[:, 1] > 0.03) & in_rects((tlo[:, 0] + thi[:, 0]) / 2, (tlo[:, 2] + thi[:, 2]) / 2)
hitv = np.zeros(len(tris), bool)
for k in range(0, len(tris), 2000):
    sl = slice(k, k + 2000)
    hitv[sl] = np.any(np.all(thi[sl, None, :] >= vlo[None], 2) & np.all(tlo[sl, None, :] <= vhi[None], 2), 1)
cand &= hitv | ground
PTS, TID = [], []
for ti in np.nonzero(cand)[0]:
    P = samples(tris[ti]); PTS.append(P); TID.append(np.full(len(P), ti))
P = np.concatenate(PTS); TID = np.concatenate(TID)
inb = (P[:, 1] > 0.03) & (P[:, 1] < 2.05) & in_rects(P[:, 0], P[:, 2])
for k in range(0, len(P), 400000):
    sl = slice(k, k + 400000)
    inb[sl] |= np.any(np.all(P[sl, None, :] >= vlo[None], 2) & np.all(P[sl, None, :] <= vhi[None], 2), 1)
P, TID = P[inb], TID[inb]
print('sampled %d triangles -> %d points' % (cand.sum(), len(P)))
cls = np.concatenate([classify(P[k:k + 400000]) for k in range(0, len(P), 400000)])
hit = cls > 0
skin = np.zeros(len(P), bool)
skin[hit] = wall_skin(P[hit])
fl = cls == 5                                         # stair / flight volumes: only the 11 cm cladding skin is flush
skin[fl] = wall_skin(P[fl], 0.12) if fl.any() else skin[fl]
report = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}}
for k in (1, 5, 2, 3, 4):
    m = (cls == k) & ~skin
    for ti in np.unique(TID[m]):
        mm = m & (TID == ti)
        nm = str(names[ti])
        e = report[k].setdefault(nm, {'samples': 0, 'lo': P[mm].min(0), 'hi': P[mm].max(0)})
        e['samples'] += int(mm.sum()); e['lo'] = np.minimum(e['lo'], P[mm].min(0)); e['hi'] = np.maximum(e['hi'], P[mm].max(0))

LABEL = {1: 'ROUTE CORRIDOR', 5: 'STAIR / FLIGHT VOLUME', 2: 'WALKABLE TOP', 3: 'OPENING', 4: 'DRESSING ON OPEN GROUND (allowed, listed)'}
out = {'district': D, 'triangles': int(len(tris)), 'checked_triangles': int(cand.sum()), 'routes': len(routes), 'walkable_tops': len(tops),
       'openings': len(openings), 'results': {}}
print('%s: %d triangles (%d near), %d route corridors, %d walkable tops, %d openings' % (D, len(tris), cand.sum(), len(routes), len(tops), len(openings)))
for k in (1, 5, 2, 3, 4):
    rows = [{'mesh': n, 'samples': e['samples'], 'aabb_min': np.round(e['lo'], 2).tolist(), 'aabb_max': np.round(e['hi'], 2).tolist()}
            for n, e in sorted(report[k].items(), key=lambda kv: -kv[1]['samples'])]
    out['results'][LABEL[k]] = rows
    print('%-42s %d meshes' % (LABEL[k], len(rows)))
    for r in rows[:40]:
        print('    %-70s %6d  %s .. %s' % (r['mesh'][-70:], r['samples'], r['aabb_min'], r['aabb_max']))
out['pass'] = not any(out['results'][LABEL[k]] for k in (1, 5, 2, 3))
print('PASS' if out['pass'] else 'FAIL')
json.dump(out, open('districts/%s/SELF_CHECK.json' % D, 'w'), indent=1)
