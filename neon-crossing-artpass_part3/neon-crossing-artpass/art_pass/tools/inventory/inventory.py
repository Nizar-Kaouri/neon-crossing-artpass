"""Building inventory for a district, from layout_dump.json only (Claude, cloud). Same fields the builder reads as
# Run from art_pass/:  cd art_pass && python tools/inventory/inventory.py <name> x0 z0 x1 z1 <ID prefix> <out.json>   (numpy + scipy)
ALLEY_INVENTORY.json: id, kind, name, footprint{centre_xz,width_m,depth_m}, roof{roof_y}, street_facing_sides[{normal_xz,
openings[{centre_xyz,width_m,height_m,sill_y}]}]. Openings = gaps >= 0.9 m in the ground-floor wall line at y 1.2."""
import sys, json, numpy as np
from geo import SHAPES, in_rect, solid
from slabs import slabs

def inventory(name, rect, prefix, kinds=None):
    groups = slabs(rect)
    near = [s for s in SHAPES if in_rect(s, (rect[0]-4, rect[1]-4, rect[2]+4, rect[3]+4)) and s.t in ('box', 'convex', 'cylinder')]
    out = []
    for k, g in enumerate(sorted(groups, key=lambda g: (g['lo'][2], g['lo'][0]))):
        x0, z0, x1, z1 = g['lo'][0], g['lo'][2], g['hi'][0], g['hi'][2]
        cx, cz, w, d = (x0+x1)/2, (z0+z1)/2, x1-x0, z1-z0
        top = float(g['hi'][1])
        local = [s for s in near if s.hi[0] >= x0-1 and s.lo[0] <= x1+1 and s.hi[2] >= z0-1 and s.lo[2] <= z1+1]
        sides = []
        for nx, nz in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            if nz:
                plane = z1 if nz > 0 else z0
                us = np.arange(x0 + 0.1, x1 - 0.1, 0.1)
                P = lambda u, y, inset: np.stack([u, np.full(len(u), y), np.full(len(u), plane - nz * inset)], 1)
            else:
                plane = x1 if nx > 0 else x0
                us = np.arange(z0 + 0.1, z1 - 0.1, 0.1)
                P = lambda u, y, inset: np.stack([np.full(len(u), plane - nx * inset), np.full(len(u), y), u], 1)
            wall = np.zeros(len(us), bool)
            for inset in (0.1, 0.3, 0.6, 1.0, 1.5):          # walls can sit a little inside the slab edge
                wall |= solid(P(us, 1.2, inset), local)
            # outside open? (street-facing) sample 3 m out at y 1.2
            outside = solid(P(us, 1.2, -3.0), near).mean() < 0.5
            openings = []
            if wall.mean() > 0.3:                              # this side has a ground-floor wall line
                gap = ~wall
                i = 0
                while i < len(us):
                    if gap[i]:
                        j = i
                        while j < len(us) and gap[j]: j += 1
                        wdt = (j - i) * 0.1
                        if 0.9 <= wdt <= 8.0 and i > 0 and j < len(us):
                            u = float((us[i] + us[j-1]) / 2)
                            col = np.array([u])
                            hgt = 2.2
                            for y in np.arange(1.4, 6.0, 0.1):    # lintel height
                                if any(solid(P(col, y, inset), local)[0] for inset in (0.1, 0.3, 0.6, 1.0)):
                                    hgt = float(y); break
                            c = [u, hgt/2, plane] if nz else [plane, hgt/2, u]
                            openings.append({'centre_xyz': [round(v, 3) for v in c], 'width_m': round(wdt, 2), 'height_m': round(hgt, 2), 'sill_y': 0.0})
                        i = j
                    else:
                        i += 1
            if openings or outside:
                sides.append({'normal_xz': [nx, nz], 'street': bool(outside), 'wall_cover': round(float(wall.mean()), 2), 'openings': openings})
        kind = (kinds(top, w, d) if kinds else ('tower' if top > 30 else 'midrise'))
        out.append({'id': '%s%02d' % (prefix, k + 1), 'kind': kind, 'name': '', 'footprint': {'centre_xz': [round(cx, 3), round(cz, 3)], 'width_m': round(w, 2), 'depth_m': round(d, 2)},
                    'roof': {'roof_y': round(top, 2)}, 'street_facing_sides': sides, 'dump_shapes': [m.i for m in g['m']]})
    return {'schema_version': 1, 'district': name, 'source': 'layout_dump.json (Claude, geometric extraction: slab clusters + ground-floor wall gap scan)',
            'region': {'x': [rect[0], rect[2]], 'z': [rect[1], rect[3]]}, 'buildings': out,
            'known_limits': 'axis-aligned footprints only; openings = gaps >= 0.9 m at y 1.2 within 1.5 m of the slab edge; names unknown; kinds by height'}
if __name__ == '__main__':
    r = list(map(float, sys.argv[2:6]))
    inv = inventory(sys.argv[1], r, sys.argv[6])
    json.dump(inv, open(sys.argv[7], 'w'), indent=1)
    for b in inv['buildings']:
        print(b['id'], b['kind'], b['footprint'], b['roof'], [(s['normal_xz'], s['street'], s['wall_cover'], len(s['openings'])) for s in b['street_facing_sides']])
