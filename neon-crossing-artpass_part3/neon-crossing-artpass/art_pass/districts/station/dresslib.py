"""Shared helpers for the station + underground district generators (Claude, cloud).
Run the generators from art_pass/ (they put tools/inventory on sys.path). Pure dump geometry, no Godot."""
import sys, json, numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import S, SHAPES, basis, local_pts          # noqa: E402
from scipy.spatial import ConvexHull                 # noqa: E402

BY_I = {sh.i: sh for sh in SHAPES}
R = lambda v, n=3: [round(float(x), n) for x in v]


def entry(i, role, **kw):
    sh = BY_I[i]
    d = {'dump_index': i, 'role': role, 'type': sh.t, 'path': S[i]['path'], 'aabb_min': R(sh.lo), 'aabb_max': R(sh.hi)}
    d.update(kw)
    return d


def is_slab(sh):
    """Plain foundation slabs (y -5..-1 and -1..0) and the deep floor grid (y -6..-5)."""
    return sh.t == 'box' and any(abs(sh.lo[1] - a) < 0.05 and abs(sh.hi[1] - b) < 0.05 for a, b in ((-5, -1), (-1, 0), (-6, -5)))


def solid_at(p, pad=0.0, shapes=None):
    p = np.atleast_2d(p)
    out = np.zeros(len(p), bool)
    for sh in (shapes if shapes is not None else SHAPES):
        if sh.t == 'concave':
            continue
        out |= sh.inside(p, pad)
    return out


def stair_axis(i):
    """Walking axis of a ramp collider (convex): uphill direction, width, along range, surface y at both ends.
    Same fields as the shrine's stair_flight (alley_builder._structure_props draws the steps from them)."""
    s = S[i]
    B, o = basis(s)
    w = local_pts(s) @ B + o
    eqs = [e for e in ConvexHull(w).equations if 0.2 < e[1] < 0.99]
    # the walking surface = the sloped face with the highest points (top of the ramp prism)
    best = None
    for q in eqs:
        dist = np.abs(w @ q[:3] + q[3])
        on = w[dist < 1e-3]
        if len(on) >= 3 and (best is None or on[:, 1].mean() > best[1]):
            best = (q, on[:, 1].mean())
    n = best[0][:3]; d = best[0][3]
    dirv = -np.array([n[0], n[2]]); dirv /= np.linalg.norm(dirv)
    perp = np.array([-dirv[1], dirv[0]])
    a = w[:, [0, 2]].mean(0)
    rel = w[:, [0, 2]] - a
    across, along = rel @ perp, rel @ dirv
    mid = (across.max() + across.min()) / 2
    def surf(t):
        q = a + dirv * t + perp * mid
        return float(-(n[0] * q[0] + n[2] * q[1] + d) / n[1])
    a0, a1 = float(along.min()), float(along.max())
    return {'width_true': round(float(across.max() - across.min()), 3),
            'axis': {'origin_xz': R(a), 'dir_xz': R(dirv, 4), 'mid_across': round(float(mid), 3), 'along_min': round(a0, 3),
                     'along_max': round(a1, 3), 'y_low': round(surf(a0), 3), 'y_high': round(surf(a1), 3)},
            'plane': R(list(n) + [d], 5)}


# ------------------------------------------------------------------ kit placement (kit fronts face +Z, origin bottom-left)
def rot_for(n):
    return round(float(np.degrees(np.arctan2(n[0], n[2]))), 2)


def xdir(rot):
    t = np.radians(rot)
    return np.array([np.cos(t), 0.0, -np.sin(t)])


def wall_piece(piece, centre, n, width, y, out, aabb_h, depth_back=0.0, **kw):
    """A kit piece whose local x spans 0..width, mounted on a wall: centre = point on the wall face (x, z),
    n = outward normal, out = gap between wall face and the piece's BACK. Returns a prop dict with its world AABB."""
    n = np.array([n[0], 0.0, n[1]]); rot = rot_for(n)
    face = np.array([centre[0], y, centre[1]])
    front = face + n * (out + depth_back)
    org = front - xdir(rot) * (width / 2)
    p = {'piece': piece, 'pos': R(org), 'rot': rot}
    p.update(kw)
    back = face + n * out
    lo = np.minimum(back - xdir(rot) * width / 2, front + xdir(rot) * width / 2)
    hi = np.maximum(back + xdir(rot) * width / 2, front - xdir(rot) * width / 2)
    p['aabb'] = [R(lo), R(hi + np.array([0, aabb_h, 0]))]
    return p


def centred_piece(piece, pos, rot, lo, hi, **kw):
    """A prop with its origin at its own centre (lanterns, lamps, posters); lo/hi = its local AABB."""
    p = {'piece': piece, 'pos': R(pos), 'rot': rot}
    p.update(kw)
    t = np.radians(rot); c, s = np.cos(t), np.sin(t)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    wc = np.stack([corners[:, 0] * c + corners[:, 2] * s, corners[:, 1], -corners[:, 0] * s + corners[:, 2] * c], 1) + np.array(pos)
    p['aabb'] = [R(wc.min(0)), R(wc.max(0))]
    return p


PIECE = {   # local AABBs (from the GLBs) of the pieces placed here
    'P_lantern_paper': ([-0.23, -0.63, -0.23], [0.23, 0.01, 0.23]),
    'P_wall_lamp': ([-0.08, -0.12, 0.0], [0.08, 0.13, 0.15]),
    'P_poster': ([-0.25, 0.0, 0.0], [0.25, 0.5, 0.01]),
    'P_pot_round': ([-0.26, 0.0, -0.25], [0.26, 0.45, 0.25]),
    'F_pot_plant': ([-0.39, 0.4, -0.39], [0.39, 1.3, 0.39]),
    'G_tactile_dots_1m': ([0.0, -0.1, -1.0], [0.3, 0.0, 0.0]),
    'G_tactile_ribs_1m': ([0.0, -0.1, -1.0], [0.3, 0.0, 0.0]),
}


def prop(piece, pos, rot=0.0, **kw):
    lo, hi = PIECE[piece]
    return centred_piece(piece, pos, rot, lo, hi, **kw)


def wall_mount(piece, x, y, z, n, out=0.05, **kw):
    """Centred wall prop (lamp, poster): back `out` metres off the wall face at (x, z), facing n=(nx, nz)."""
    rot = rot_for([n[0], 0, n[1]])
    return prop(piece, [x + n[0] * out, y, z + n[1] * out], rot, **kw)


def hulls(rect, out):
    import subprocess
    subprocess.run([sys.executable, 'tools/convex_hulls.py'] + [str(v) for v in rect] + [out], check=True)


def save(inv, path):
    json.dump(inv, open(path, 'w'), indent=1)
