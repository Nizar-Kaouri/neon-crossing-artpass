"""Street dressing for a building district (Claude). Visual only, no collision:
A  old small boxes (crates / machines / boxes the old map already has collision for) -> matching props, old box hidden
B  AC units on facades: between upper windows (under the sill line) and above ground-floor doors, never over openings
C  drain grates flush in the ground along street faces, never in front of openings
D  overhead cable bundles between facing buildings across a street, >= 5 m up
Usage (from art_pass/): python tools/inventory/street_dress.py <INVENTORY.json> <out STREET_DRESS.json> [seed]"""
import sys, json, math, random
import numpy as np
from geo import S, SHAPES

PIECES = {  # name: (sx, sy, sz) of the mesh
    'H_vending_machine': (1.03, 1.84, 0.67), 'P_utility_box': (0.8, 1.4, 0.53), 'P_bin': (0.54, 0.96, 0.44),
    'P_crates_stack': (1.14, 0.62, 0.4), 'P_ac_unit': (0.84, 0.6, 0.31), 'G_drain_grate': (0.6, 0.1, 0.4),
    'P_cable_bundle_6m': (6.01, 0.64, 0.16)}

def yaw_of(n):  # piece front (+z) faces along n
    return math.degrees(math.atan2(n[0], n[1]))

def main(inv_path, out_path, seed=7):
    rnd = random.Random(seed)
    inv = json.load(open(inv_path))
    B = [b for b in inv['buildings']]
    rects = {b['id']: (b['footprint']['centre_xz'][0] - b['footprint']['width_m'] / 2, b['footprint']['centre_xz'][1] - b['footprint']['depth_m'] / 2,
                       b['footprint']['centre_xz'][0] + b['footprint']['width_m'] / 2, b['footprint']['centre_xz'][1] + b['footprint']['depth_m'] / 2) for b in B}
    reg = inv.get('region', {})
    if 'rects' in reg: R = reg['rects']
    else: R = [[reg['x'][0], reg['z'][0], reg['x'][1], reg['z'][1]]]
    def in_region(x, z): return any(r[0] <= x < r[2] and r[1] <= z < r[3] for r in R)
    def in_any_building(x, z, grow=0.0, skip=None):
        for k, r in rects.items():
            if k != skip and r[0] - grow < x < r[2] + grow and r[1] - grow < z < r[3] + grow: return True
        return False
    props, hide = [], []
    ops = []                                                                   # opening prisms (generous: 1.0 m deep, +0.3 m wide)
    for b in B:
        for sd in b.get('street_facing_sides', []):
            nz = abs(sd['normal_xz'][1]) > 0.5
            for o in sd['openings']:
                u = o['centre_xyz'][0] if nz else o['centre_xyz'][2]; pl = o['centre_xyz'][2] if nz else o['centre_xyz'][0]
                ops.append((nz, pl, u - o['width_m'] / 2 - 0.3, u + o['width_m'] / 2 + 0.3))
    def in_opening(lo, hi):
        for nz, pl, u0, u1 in ops:
            a0, a1 = (lo[0], hi[0]) if nz else (lo[2], hi[2])
            w0, w1 = (lo[2], hi[2]) if nz else (lo[0], hi[0])
            if a1 > u0 and a0 < u1 and w1 > pl - 1.0 and w0 < pl + 1.0: return True
        return False

    # A: retained small boxes
    for sh in SHAPES:
        if sh.t != 'box': continue
        c = (sh.lo + sh.hi) / 2
        if not in_region(c[0], c[2]) or not (-0.05 <= sh.lo[1] <= 0.3): continue
        size = np.array(S[sh.i]['size']) * np.linalg.norm(sh.B, axis=1)
        sx, sy, sz = size
        if sy < 0.45 or sy > 2.3 or max(sx, sz) > 2.0 or min(sx, sz) < 0.25: continue
        if in_any_building(c[0], c[2], grow=-0.15): continue                  # interiors stay as they are
        if in_opening(sh.lo, sh.hi): continue                                 # T36: a box in a doorway keeps its plain old look
        rot90 = sz > sx                                                        # long side along local x
        L, D = (sz, sx) if rot90 else (sx, sz)
        if sy >= 1.5 and L <= 1.5: piece = 'H_vending_machine'
        elif sy >= 1.1 and L <= 1.1: piece = 'P_utility_box'
        elif sy >= 0.7 and L <= 0.75: piece = 'P_bin'
        elif sy <= 1.0: piece = 'P_crates_stack'
        else: continue
        p = PIECES[piece]
        sc = [L / p[0], sy / p[1], D / p[2]]
        if min(sc) < 0.55 or max(sc) > 1.8: continue
        bx = sh.B[0] / np.linalg.norm(sh.B[0])
        yaw = math.degrees(math.atan2(-bx[2], bx[0])) + (90.0 if rot90 else 0.0)
        props.append({'piece': piece, 'pos': [round(c[0], 3), round(sh.lo[1], 3), round(c[2], 3)], 'rot': round(yaw, 2), 'scale': [round(v, 3) for v in sc], 'replaces': sh.i})
        hide.append(sh.i)

    # faces of every building (skip faces inside / pressed against a neighbour)
    faces = []
    for b in B:
        (x0, z0, x1, z1) = rects[b['id']]; H = float(b['roof']['roof_y'])
        for n, plane, u0, u1 in [((0, 1), z1, x0, x1), ((0, -1), z0, x0, x1), ((1, 0), x1, z0, z1), ((-1, 0), x0, z0, z1)]:
            mid = (u0 + u1) / 2
            px, pz = (mid, plane + n[1] * 0.6) if n[1] else (plane + n[0] * 0.6, mid)
            if in_any_building(px, pz, skip=b['id']): continue                 # neighbour within 0.6 m: hidden face
            holes = []
            for sd in b.get('street_facing_sides', []):
                if tuple(sd['normal_xz']) != n: continue
                for o in sd['openings']:
                    u = o['centre_xyz'][0] if n[1] else o['centre_xyz'][2]
                    holes.append((u - o['width_m'] / 2, u + o['width_m'] / 2, float(o.get('sill_y', 0)) + o['height_m']))
            faces.append({'b': b, 'n': n, 'plane': plane, 'u0': u0, 'u1': u1, 'H': H, 'holes': holes,
                          'street': any(tuple(sd['normal_xz']) == n and sd.get('street', True) for sd in b.get('street_facing_sides', []))})
    def free(f, u, half, margin=0.3):
        return all(u + half < h0 - margin or u - half > h1 + margin for h0, h1, _ in f['holes'])
    def world(f, u, y, out):
        n = f['n']
        return [round(u, 3), round(y, 3), round(f['plane'] + n[1] * out, 3)] if n[1] else [round(f['plane'] + n[0] * out, 3), round(y, 3), round(u, 3)]

    for f in faces:
        span = f['u1'] - f['u0']; H = f['H']; rot = round(yaw_of(f['n']), 2)
        if f['b']['kind'] in ('shrine',) or span < 2.5: continue
        # B: AC units. Upper floors: between windows, below the sill; ground floor: above the doors' lintel line
        count = max(1, int((span - 0.8) / 2.6)); pitch = span / count
        lv = 1
        while lv * 3.1 + 2.6 < min(H, 16.0):                               # T36: AC units only on the lower 4 floors, sparser
            for k in range(1, count):
                if rnd.random() < 0.13:
                    u = f['u0'] + pitch * k
                    props.append({'piece': 'P_ac_unit', 'pos': world(f, u, lv * 3.1 + 0.2, 0.22), 'rot': rot, 'scale': [0.8, 0.8, 0.8]})
            lv += 1
        if H > 4.0:
            for k in range(count):
                u = f['u0'] + pitch * (k + 0.5)
                top = max([h[2] for h in f['holes']] + [2.4])
                if rnd.random() < 0.3 and free(f, u, 0.5, 0.2):
                    props.append({'piece': 'P_ac_unit', 'pos': world(f, u, max(2.55, top + 0.25), 0.22), 'rot': rot, 'scale': [0.8, 0.8, 0.8]})
        # C: drain grates along street faces, 0.55 m out, flush with the ground
        if f['street']:
            u = f['u0'] + 2.0
            while u < f['u1'] - 1.5:
                if free(f, u, 0.4, 0.8):
                    p = world(f, u, 0.004, 0.75)
                    if not in_any_building(p[0], p[2]):
                        props.append({'piece': 'G_drain_grate', 'pos': p, 'rot': rot, 'scale': [1, 1, 1]})
                u += rnd.uniform(6.0, 9.0)

    # D: cables between facing faces across a street
    for i, a in enumerate(faces):
        for b_ in faces[i + 1:]:
            if a['b'] is b_['b'] or a['n'][0] != -b_['n'][0] or a['n'][1] != -b_['n'][1]: continue
            gap = (b_['plane'] - a['plane']) * (a['n'][1] or a['n'][0])
            if not (5.0 <= gap <= 16.0): continue
            lo, hi = max(a['u0'], b_['u0']), min(a['u1'], b_['u1'])
            if hi - lo < 2.0: continue
            y = min(a['H'], b_['H'], 7.6) - 0.6
            if y < 5.2: continue
            for k in range(1 if hi - lo < 12 else 2):
                u = lo + (hi - lo) * ((k + 1) / ((1 if hi - lo < 12 else 2) + 1)) + rnd.uniform(-0.8, 0.8)
                start = world(a, u, y + rnd.uniform(-0.2, 0.3), 0.06)
                d = a['n']
                yaw = math.degrees(math.atan2(-d[1], d[0]))                     # local +x -> across the street
                props.append({'piece': 'P_cable_bundle_6m', 'pos': start, 'rot': round(yaw, 2), 'scale': [round((gap - 0.12) / 6.01, 3), 1, 1]})
    out = {'note': 'STREET_DRESS (Claude): visual-only props; "hide" = old box visuals replaced by a matching prop (collision unchanged)',
           'inventory': inv_path, 'hide': sorted(set(hide)), 'props': props}
    json.dump(out, open(out_path, 'w'), indent=1)
    from collections import Counter
    print(out_path, Counter(p['piece'] for p in props), 'hidden boxes', len(hide))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 7)
