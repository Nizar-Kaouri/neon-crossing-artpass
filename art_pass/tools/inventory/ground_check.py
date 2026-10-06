"""Self-check of the ground pass (Claude, cloud): re-reads districts/<d>/GROUND_DETAIL.json and tests every box against a
fresh, finer probe (5 cm) of the old collision and the inventory, independently of how ground_detail.py placed it.
Fails (exit 1) on any of:
  height     top not within level + 0.5 .. 2.0 cm, or two layers that overlap closer than 5 mm
  ground     any 5 cm sample of the box not over the old flat ground slab (top = level +- 1 mm): ramps, roofs, steps
  obstacle   any sample closer than 0.25 m to a collider standing on the ground (walls, stairs, landings, kerbs ...)
  covered    any sample under a roof / ceiling / lintel lower than 6 m (surface districts; underground: its tunnel)
  volumes    box touches a stair / landing / terrace / ramp / escalator volume, a building footprint, an opening
             (1 m in front of it), a ground patch (lawn / path), a floor panel or a ground prop
  overlap    two boxes of the same layer overlap
Writes districts/<d>/GROUND_SELF_CHECK.json.  Usage (from art_pass/): python tools/inventory/ground_check.py [district ...]"""
import sys, json, math
import numpy as np
from scipy import ndimage as ndi
from ground_probe import Grid
from ground_detail import CFG, INV_NAME, LAYER, exclusions

RES = 0.05


def obb(it):
    _, cx, cz, sx, sz, top, yaw = it
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return np.array([(cx + c * u * sx / 2 + s * v * sz / 2, cz - s * u * sx / 2 + c * v * sz / 2) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


def samples(it, inset=0.002):
    _, cx, cz, sx, sz, top, yaw = it
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    us = np.linspace(-sx / 2 + inset, sx / 2 - inset, max(2, int(sx / RES) + 2))
    vs = np.linspace(-sz / 2 + inset, sz / 2 - inset, max(2, int(sz / RES) + 2))
    U, V = np.meshgrid(us, vs)
    return np.stack([cx + c * U + s * V, cz - s * U + c * V], -1).reshape(-1, 2)


def sat_overlap(a, b, eps=1e-4):
    for poly in (a, b):
        for j in range(4):
            e = poly[(j + 1) % 4] - poly[j]; n = np.array([-e[1], e[0]]); n /= np.linalg.norm(n)
            pa, pb = a @ n, b @ n
            if pa.max() <= pb.min() + eps or pb.max() <= pa.min() + eps:
                return False
    return True


def check(d):
    cfg = CFG[d]; level = cfg['level']
    gd = json.load(open(f'districts/{d}/GROUND_DETAIL.json'))
    inv = json.load(open(INV_NAME[d]))
    items = gd['items']
    fails = {k: [] for k in ('height', 'ground', 'obstacle', 'covered', 'volumes', 'overlap')}
    if not items:
        return {'district': d, 'boxes': 0, 'fails': fails, 'ok': True}
    P = np.concatenate([obb(it) for it in items])
    bb = [P[:, 0].min() - 1.0, P[:, 1].min() - 1.0, P[:, 0].max() + 1.0, P[:, 1].max() + 1.0]
    g = Grid(bb, level, res=RES).build()
    ground = np.isfinite(g.gtop) & (np.abs(g.gtop - level) <= 0.001)
    near_obst = ndi.distance_transform_edt(~g.block) * RES < 0.25
    covered = g.cover < level + (4.5 if cfg.get('allow_cover') else cfg.get('cover_max', 6.0))
    ex = exclusions(d, inv, level)
    # volumes without the generator's safety margins (raw): footprints, openings (1 m out), stairs, patches, props
    exr = []
    for a, c, b, e, why in ex:
        m = 0.5 if any(k in why for k in ('stair', 'landing', 'terrace', 'ramp', 'escalator')) else (0.2 if why.startswith('building') else 0.0)
        exr.append((a + m, c + m, b - m, e - m, why))
    for n, it in enumerate(items):
        top = it[5]
        if not (level + 0.005 - 1e-6 <= top <= level + 0.020 + 1e-6):
            fails['height'].append([n, top])
        S = samples(it)
        i = np.floor((S[:, 0] - g.x0) / RES).astype(int); k = np.floor((S[:, 1] - g.z0) / RES).astype(int)
        if not ground[k, i].all():
            fails['ground'].append([n, it[1:5]])
        if near_obst[k, i].any():
            fails['obstacle'].append([n, it[1:5]])
        if covered[k, i].any() and not cfg.get('allow_cover'):
            fails['covered'].append([n, it[1:5]])
        if cfg.get('allow_cover') and not covered[k, i].all():
            fails['covered'].append([n, 'underground box not in the tunnel', it[1:5]])
        lo = S.min(0); hi = S.max(0)
        for a, c, b, e, why in exr:
            if lo[0] < b and hi[0] > a and lo[1] < e and hi[1] > c:
                inside = (S[:, 0] > a) & (S[:, 0] < b) & (S[:, 1] > c) & (S[:, 1] < e)
                if inside.any():
                    fails['volumes'].append([n, why, it[1:5]])
    # overlaps: same layer -> never; different layers -> >= 5 mm apart (guaranteed by LAYER, checked anyway)
    polys = [obb(it) for it in items]
    boxes = np.array([[p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()] for p in polys])
    order = np.argsort(boxes[:, 0])
    pairs = 0
    for ai in range(len(order)):
        a = order[ai]
        for bi in range(ai + 1, len(order)):
            b = order[bi]
            if boxes[b, 0] >= boxes[a, 2]:
                break
            if boxes[b, 1] >= boxes[a, 3] or boxes[a, 1] >= boxes[b, 3]:
                continue
            if not sat_overlap(polys[a], polys[b]):
                continue
            pairs += 1
            dy = abs(items[a][5] - items[b][5])
            if dy < 0.005 - 1e-6:
                fails['overlap'].append([int(a), int(b), round(dy, 4)])
    mats = gd['mat_ids']
    per_mat = {}
    for it in items:
        per_mat[mats[it[0]]] = per_mat.get(mats[it[0]], 0) + 1
    mc = gd.get('merge_cell', 48.0)
    cells = {(it[0], math.floor(it[1] / mc), math.floor(it[2] / mc)) for it in items}
    res = {'district': d, 'boxes': len(items), 'boxes_per_material': per_mat, 'meshes_after_merge': len(cells),
           'top_y_range_above_level': [round(min(it[5] for it in items) - level, 4), round(max(it[5] for it in items) - level, 4)],
           'cross_layer_overlaps': pairs, 'fails': {k: v[:20] for k, v in fails.items()}, 'fail_counts': {k: len(v) for k, v in fails.items()},
           'ok': not any(fails.values())}
    return res


def main(names):
    bad = 0
    for d in names or list(CFG):
        r = check(d)
        json.dump(r, open(f'districts/{d}/GROUND_SELF_CHECK.json', 'w'), indent=1)
        print('GROUND CHECK %-11s %s boxes=%d meshes=%d top=%s fails=%s' % (d, 'OK  ' if r['ok'] else 'FAIL', r['boxes'], r.get('meshes_after_merge', 0),
                                                                     r.get('top_y_range_above_level'), r.get('fail_counts')))
        bad += not r['ok']
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
