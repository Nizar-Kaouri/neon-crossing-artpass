import json, numpy as np
from geo import S, SHAPES, basis, local_pts
inv = json.load(open('SHRINE_INVENTORY.json'))
near = [sh for sh in SHAPES if sh.hi[0] > 20 and sh.lo[0] < 105 and sh.hi[2] > -90 and sh.lo[2] < -40]
tris = []
for sh in near:
    if sh.t == 'concave':
        w = local_pts(sh.s) @ sh.B + sh.o
        tris.append(w.reshape(-1, 3, 3))
tris = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
def ground(x, z, top):
    best = -1e9
    # concave: vertical ray down from top
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    v0 = b - a; v1 = c - a; p = np.array([x, 0, z])
    d00 = v0[:, 0]**2 + v0[:, 2]**2; d01 = v0[:, 0]*v1[:, 0] + v0[:, 2]*v1[:, 2]; d11 = v1[:, 0]**2 + v1[:, 2]**2
    vp = p - a; d20 = vp[:, 0]*v0[:, 0] + vp[:, 2]*v0[:, 2]; d21 = vp[:, 0]*v1[:, 0] + vp[:, 2]*v1[:, 2]
    den = d00*d11 - d01*d01; den[np.abs(den) < 1e-12] = 1e-12
    v = (d11*d20 - d01*d21)/den; w = (d00*d21 - d01*d20)/den; u = 1 - v - w
    m = (u >= -1e-6) & (v >= -1e-6) & (w >= -1e-6)
    if m.any():
        y = (u*a[:, 1] + v*b[:, 1] + w*c[:, 1])[m]; y = y[y <= top + 0.01]
        if len(y): best = max(best, y.max())
    ys = np.arange(top, -0.6, -0.02)
    P = np.stack([np.full(len(ys), x), ys, np.full(len(ys), z)], 1)
    for sh in near:
        if sh.t in ('box', 'convex', 'cylinder') and sh.lo[0] <= x <= sh.hi[0] and sh.lo[2] <= z <= sh.hi[2]:
            ins = sh.inside(P)
            if ins.any(): best = max(best, ys[np.argmax(ins)])
    return best if best > -1e8 else 0.0
props = []
for st in inv['structures']:
    if st['role'] != 'stair_flight': continue
    s = S[st['dump_index']]; B, o = basis(s); w = local_pts(s) @ B + o
    from scipy.spatial import ConvexHull
    eqs = [e for e in ConvexHull(w).equations if 0.2 < e[1] < 0.99]
    n = eqs[0][:3]
    dirv = -np.array([n[0], n[2]]); dirv /= np.linalg.norm(dirv); perp = np.array([-dirv[1], dirv[0]])
    a = w[:, [0, 2]].mean(0)
    rel = w[:, [0, 2]] - a
    across = rel @ perp; along = rel @ dirv
    lo_e = {'y': float(max(w[:, 1].min(), 0.0))}; hi_e = {'y': float(w[:, 1].max())}
    if w[:, 1].min() < 0: lo_e['y'] = 0.0
    lo_e['y'] = round(float(w[:, 1].min()) if w[:, 1].min() > 0.5 else 0.0, 3)
    st['width_true'] = round(float(across.max() - across.min()), 3)
    st['axis'] = {'origin_xz': a.round(3).tolist(), 'dir_xz': dirv.round(4).tolist(), 'mid_across': round(float((across.max() + across.min()) / 2), 3),
                  'along_min': round(float(along.min()), 3), 'along_max': round(float(along.max()), 3), 'y_low': lo_e['y'], 'y_high': hi_e['y']}
    yaw = float(np.degrees(np.arctan2(dirv[0], dirv[1])))
    for t, ey in ((float(along.min()) + 0.4, lo_e['y']), (float(along.max()) - 0.4, hi_e['y'])):
        for side in (-1, 1):
            q = a + dirv * t + perp * (st['axis']['mid_across'] + side * (st['width_true'] / 2 + 0.55))
            g = ground(q[0], q[1], ey + 0.6)
            ok = abs(g - ey) < 1.2
            props.append({'piece': 'H_stone_lantern', 'pos': [round(q[0], 3), round(g, 3), round(q[1], 3)], 'rot': round(yaw, 1), 'for': st['dump_index'], 'ground_ok': bool(ok)})
for st in inv['structures']:
    if st['role'] == 'tree_trunk':
        lo, hi = st['aabb_min'], st['aabb_max']
        props.append({'piece': 'F_pine_cloud', 'pos': [round((lo[0]+hi[0])/2, 3), round(hi[1] - 0.4, 3), round((lo[2]+hi[2])/2, 3)], 'rot': 0.0})
inv['props'] = props
json.dump(inv, open('SHRINE_INVENTORY.json', 'w'), indent=1)
for p in props: print(p)
for st in inv['structures']:
    if st['role'] == 'stair_flight': print(st['dump_index'], st['width_true'], st['axis'])
