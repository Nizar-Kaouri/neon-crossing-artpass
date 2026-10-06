"""MALL inventory (Claude, cloud). Non-building district: every old collider in the mall region gets a structure role
(floors, atrium edge, shop fronts, escalators, stairs, facade...). Also computes the visual-only dressing positions the
builder places (shop signs flush on the shop fronts, two screens flush on the outer wall, baked lights) so they can be
checked by self_check.py before the PR.
Run from art_pass/:  python districts/mall/tools/mall_inventory.py   (numpy + scipy; about 1 minute)
Output: districts/mall/MALL_INVENTORY.json"""
import json, sys, collections, os
import numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import SHAPES, solid, local_pts

RECT = (-72, 30, 2, 125)
CX, CZ, A, B = -35.0, 81.0, 30.0, 48.0          # outer ellipse of the mall (roof ring: x -65..-5, z 33..129)
LEVELS = [0.0, 5.5, 11.0]                          # promenade floor tops; roof deck 15.0; basement floor -5.0
OUT = 'districts/mall/MALL_INVENTORY.json'


def rr(p):
    p = np.atleast_2d(p)
    return np.sqrt(((p[:, 0] - CX) / A) ** 2 + ((p[:, 2] - CZ) / B) ** 2)


def near(a, b, tol=0.03):
    return abs(a - b) <= tol


def level_of(y):
    return int(np.argmin([abs(y - l) for l in LEVELS]))


def classify(s):
    """role, level for one collider (s = geo.Shape)."""
    p = s.s.get('path', '')
    lo, hi = float(s.lo[1]), float(s.hi[1])
    c = (s.lo + s.hi) / 2
    w = local_pts(s.s) @ s.B + s.o
    r = rr(w); rmin, rmax, rc = float(r.min()), float(r.max()), float(rr(c)[0])
    sz = s.hi - s.lo
    if hi < -1.5:
        return 'underground', -1
    if 'ModularCafeCollision' in p:
        return 'cafe_fixture', -1
    if 'MallFacadeSample' in p:
        if s.t == 'convex':
            return 'entrance_canopy', 0
        if sz[1] > 2.55 and min(sz[0], sz[2]) < 0.2 and max(sz[0], sz[2]) < 0.2:
            return 'mullion', level_of(lo - 0.8)
        if near(sz[1], 2.52, 0.05):
            return 'facade_glass', level_of(lo - 0.8)
        if sz[1] > 5.0:
            return 'mast', 0                                       # tall thin poles beside the facade
        return 'facade_sill', 0
    if 'MallStaticCollision' not in p:
        if hi <= 0.05:
            return 'ground', 0
        return 'misc', 0
    if s.t == 'convex':
        for L in LEVELS:
            if near(lo, L - 0.32) and near(hi, L):
                return ('plaza' if rmin > 0.98 else 'floor_slab'), level_of(L)
            if near(lo, L) and near(hi, L + 0.14):
                return 'atrium_curb', level_of(L)
            if near(lo, L + 0.84) and near(hi, L + 1.02):
                return 'atrium_rail', level_of(L)
            if near(lo, L) and near(hi, L + 3.84):
                return 'shop_front', level_of(L)
            if near(lo, L + 3.84) and near(hi, L + 4.0):
                return ('roof' if L > 10 else 'shop_ceiling'), level_of(L)
        if near(lo, -0.5) and near(hi, 0.0):
            return 'plaza', 0
        if rmin > 0.97 and hi > 10:
            return 'outer_wall', 0
        if rmin > 0.97 and hi <= 0.0:
            return 'basement_wall', -1
        if hi - lo > 4.0 and any(near(hi, L, 0.05) for L in LEVELS):
            return 'escalator', level_of(hi) - 1
        if rc < 0.7:
            return 'escalator_balustrade', level_of(lo)
        return 'misc', level_of(lo)
    # boxes / cylinders of the mall body
    hz = sorted([float(sz[0]), float(sz[2])])
    if near(hi, 15.1, 0.1) and rc < 0.3:
        return 'roof_bridge', 2
    if sz[1] > 10:
        return 'column', 0
    if rc < 0.77 and hz[1] <= 0.15 and sz[1] <= 1.2:
        return 'atrium_rail', level_of(lo)                       # rail posts along the atrium edge
    if rc < 0.52:
        if hz[0] >= 2.0 and sz[1] <= 0.6:
            return 'atrium_platform', level_of(lo)               # parkour platforms hanging in the atrium
        return 'escalator_handrail', level_of(lo)                # sloped handrails / side rails of the travelators
    if rc >= 0.77:
        return 'shop_fixture', level_of(lo)
    return 'promenade_furniture', level_of(lo)


def main():
    shapes = [s for s in SHAPES if RECT[0] <= (s.lo[0] + s.hi[0]) / 2 < RECT[2] and RECT[1] <= (s.lo[2] + s.hi[2]) / 2 < RECT[3]]
    structures = []
    for s in shapes:
        role, lvl = classify(s)
        structures.append({'dump_index': s.i, 'role': role, 'level': lvl, 'type': s.t, 'path': s.s.get('path', ''),
                           'aabb_min': [round(float(v), 3) for v in s.lo], 'aabb_max': [round(float(v), 3) for v in s.hi]})
    roles = collections.Counter(st['role'] for st in structures)
    byrole = collections.defaultdict(list)
    for s, st in zip(shapes, structures):
        byrole[st['role']].append(s)

    # ---- openings: gaps in the outer wall line (entrances), measured on each floor at y +1.2 / the lintel above
    t = np.radians(np.arange(0, 360, 0.5))
    wall_sh = byrole['outer_wall'] + byrole['facade_glass'] + byrole['mullion'] + byrole['entrance_canopy']
    openings = []
    for L in LEVELS[:2]:
        P = np.stack([CX + A * 0.995 * np.sin(t), np.full(len(t), L + 1.2), CZ + B * 0.995 * np.cos(t)], 1)
        m = solid(P, wall_sh, 0.05)
        if m.mean() < 0.2:
            continue
        i = 0
        while i < len(t):
            if not m[i]:
                j = i
                while j < len(t) and not m[j]:
                    j += 1
                a0, a1 = float(np.degrees(t[i])) - 0.5, float(np.degrees(t[j - 1])) + 0.5
                mid = np.radians((a0 + a1) / 2)
                top = L + 5.5                                  # no lintel found: open up to the next floor
                for y in np.arange(L + 1.4, L + 6.0, 0.1):
                    q = np.array([[CX + A * 0.995 * np.sin(mid), y, CZ + B * 0.995 * np.cos(mid)]])
                    if solid(q, wall_sh, 0.05)[0]:
                        top = float(y)
                        break
                openings.append({'kind': 'entrance', 'level': level_of(L), 'angle_deg': [round(a0, 1), round(a1, 1)],
                                 'r_band': [0.93, 1.08], 'y': [L, round(top, 2)]})
                i = j
            else:
                i += 1
    # top floor: the outer wall stops at 11.95 (0.95 m parapet over the 11.0 floor) = the jump-out edge, open all round
    # above it; keep its top + 2.05 m clear
    openings.append({'kind': 'jump_out_edge', 'level': 2, 'angle_deg': [0, 360], 'r_band': [0.93, 1.2], 'y': [11.95, 14.0]})
    stair_vols = []
    for role in ('escalator', 'escalator_balustrade', 'escalator_handrail'):
        for s in byrole[role]:
            stair_vols.append({'role': role, 'dump_index': s.i, 'min': [round(float(v), 2) for v in s.lo],
                               'max': [round(float(s.hi[0]), 2), round(float(s.hi[1]) + 2.0, 2), round(float(s.hi[2]), 2)]})

    # ---- shop signs: flush on the shop fronts (promenade side), 2.75..3.55 m above each floor
    fronts = byrole['shop_front']
    signs = []
    k = 0
    for li, L in enumerate(LEVELS):
        for a in np.arange(12.0 + li * 9.0, 360.0, 24.0):
            th = np.radians(a)
            d = np.array([A * np.sin(th), 0, B * np.cos(th)])
            hit = None
            for f in np.arange(0.5, 0.9, 0.005):
                q = np.array([[CX + d[0] * f, L + 3.15, CZ + d[2] * f]])
                if solid(q, fronts)[0]:
                    hit = q[0]
                    break
            if hit is None:
                continue
            n = -np.array([(hit[0] - CX) / A ** 2, 0, (hit[2] - CZ) / B ** 2]); n /= np.linalg.norm(n)   # inward
            tg = np.array([n[2], 0, -n[0]])
            # wall must be behind the whole sign (no sign across a gap / opening)
            ok = True
            pts = []
            for u in np.linspace(-1.0, 1.0, 9):
                for y in (L + 2.75, L + 3.55):
                    pts.append(hit - n * 0.06 + tg * u + np.array([0, y - hit[1], 0]))
            if not solid(np.array(pts), fronts, 0.02).all():
                ok = False
            # how far in front of the wall: smallest offset so all corners are >= 5 cm outside it
            off = 0.0
            for u in np.linspace(-1.0, 1.0, 9):
                for o in np.arange(0.0, 0.4, 0.01):
                    q = hit + tg * u + n * o
                    if not solid(np.array([[q[0], L + 3.15, q[2]]]), fronts)[0]:
                        off = max(off, o)
                        break
            if not ok:
                continue
            ctr = hit + n * (off + 0.06)
            signs.append({'pos': [round(float(ctr[0]), 3), round(L + 3.15, 3), round(float(ctr[2]), 3)],
                          'normal': [round(float(n[0]), 4), 0, round(float(n[2]), 4)], 'size': [2.0, 0.8], 'cell': k % 8, 'level': li})
            k += 1

    # ---- two portrait screens on the outer wall facing the crossing, either side of the north entrance
    screens = []
    near_sh = [s for s in SHAPES if s.hi[1] > 2.0 and s.lo[1] < 11.5 and (s.hi[2] < 50 or s.lo[2] < 50)]
    for a in (146.0, 214.0):
        th = np.radians(a)
        p0 = np.array([CX + A * np.sin(th), 0, CZ + B * np.cos(th)])
        n = np.array([(p0[0] - CX) / A ** 2, 0, (p0[2] - CZ) / B ** 2]); n /= np.linalg.norm(n)       # outward
        tg = np.array([n[2], 0, -n[0]])
        W, H, y0 = 5.0, 7.5, 3.1                  # 2:3 like billboard.png; frame 2.94..10.76: above the 0.8 m sills + 2.05, below the jump-out edge (11)
        # the plane goes 6 cm outside the outermost collider point behind it (wall, glass AND the thin mullions)
        grid = np.array([p0 + tg * u + np.array([0, y, 0]) for u in np.arange(-W / 2 - 0.2, W / 2 + 0.21, 0.05)
                         for y in np.arange(y0 - 0.2, y0 + H + 0.21, 0.1)])
        off = -2.0
        for o in np.arange(1.0, -2.0, -0.01):
            if solid(grid + n * o, near_sh).any():
                off = o
                break
        ctr = p0 + n * (off + 0.06)
        screens.append({'pos': [round(float(ctr[0]), 3), round(y0 + H / 2, 3), round(float(ctr[2]), 3)],
                        'normal': [round(float(n[0]), 4), 0, round(float(n[2]), 4)], 'size': [W, H], 'angle_deg': a})

    # ---- baked lights (hidden live in the game, like every district): promenade + atrium + entrances
    lights = []
    for li, L in enumerate(LEVELS):
        for a in np.arange(0.0 + li * 30.0, 360.0, 60.0):
            th = np.radians(a)
            lights.append({'pos': [round(CX + A * 0.67 * np.sin(th), 2), L + 3.6, round(CZ + B * 0.67 * np.cos(th), 2)], 'color': 'ffcf8a', 'energy': 2.2, 'range': 12.0})
    for o in openings:
        if o['kind'] == 'entrance':
            th = np.radians(sum(o['angle_deg']) / 2)
            lights.append({'pos': [round(CX + A * 1.08 * np.sin(th), 2), o['y'][0] + 3.2, round(CZ + B * 1.08 * np.cos(th), 2)], 'color': 'ffc27a', 'energy': 2.0, 'range': 9.0})
    for s in screens:
        p = np.array(s['pos']) + np.array(s['normal']) * 3.0
        lights.append({'pos': [round(float(v), 2) for v in p], 'color': 'c070ff', 'energy': 2.5, 'range': 14.0})

    # ---- light trim on the climbable / jump-out edges (STYLE readability rule): the vertical faces of the roof ring
    # (outer and atrium side) and the outer face of the top-floor parapet (outer wall top, 11.95), 5 cm outside each face, 2 cm in from its ends
    from scipy.spatial import ConvexHull
    trims = []
    for role, side, y0, y1 in (('roof', 1, 14.86, 14.98), ('roof', -1, 14.86, 14.98), ('outer_wall', 1, 11.78, 11.93)):
        for s in byrole[role]:
            if role == 'outer_wall' and not near(float(s.hi[1]), 11.95, 0.02):
                continue
            w = local_pts(s.s) @ s.B + s.o
            h = ConvexHull(w)
            c = w.mean(0)
            for eq in h.equations:
                nrm = eq[:3]
                if abs(nrm[1]) > 0.1:
                    continue
                radial = np.array([(c[0] - CX) / A ** 2, 0, (c[2] - CZ) / B ** 2]); radial /= np.linalg.norm(radial)
                if np.dot(nrm, radial) * side < 0.7:
                    continue
                on = w[np.abs(w @ nrm + eq[3]) < 1e-3]
                if len(on) < 3:
                    continue
                tg = np.array([nrm[2], 0, -nrm[0]])
                u = on @ tg
                if u.max() - u.min() < 0.1:
                    continue
                mid = on.mean(0)
                um = (u.max() + u.min()) / 2
                ctr = mid + tg * (um - mid @ tg) + nrm * 0.05
                trims.append({'pos': [round(float(ctr[0]), 3), round((y0 + y1) / 2, 3), round(float(ctr[2]), 3)],
                              'normal': [round(float(nrm[0]), 4), 0, round(float(nrm[2]), 4)],
                              'size': [round(float(u.max() - u.min()) - 0.04, 3), round(y1 - y0, 3)], 'role': role})
                break

    inv = {'schema_version': 1, 'district': 'mall',
           'source': 'layout_dump.json (Claude, cloud): role per collider by height band + radial position in the oval',
           'region': {'rects': [list(RECT)]},
           'mall': {'centre_xz': [CX, CZ], 'semi_axes_xz': [A, B], 'promenade_levels': LEVELS, 'roof_y': 15.0, 'basement_y': -5.0,
                    'notes': 'Oval, 3 promenade floors around an open atrium (open to the sky, down to the basement at -5 = underground district). '
                             'Closed shop ring r 0.74..0.99 behind a continuous shop-front wall; outer wall with two glass rows (y 0.8-3.3, 6.3-8.8); '
                             'top floor has no outer wall = jump-out edge; escalators by the atrium link -5 / 0 / 5.5 / 11.'},
           'buildings': [], 'role_counts': dict(roles), 'structures': structures,
           'openings': openings, 'stair_volumes': stair_vols,
           'dressing': {'signs': signs, 'screens': screens, 'trims': trims, 'lights': lights},
           'known_limits': 'roles are geometric (height band + ellipse radius), checked against top-down plots; shop interiors are closed in the old map'}
    json.dump(inv, open(OUT, 'w'), indent=1)
    print(len(structures), 'structures', dict(roles))
    print(len(openings), 'openings', [(o['kind'], o['level'], o['angle_deg'], o['y']) for o in openings])
    print(len(signs), 'signs', len(screens), 'screens', screens, len(trims), 'trims', len(lights), 'lights')


if __name__ == '__main__':
    main()
