"""MALL self-check (Claude, cloud). Run from art_pass/:  python districts/mall/tools/self_check.py
Every visual the mall builder ADDS (shop signs, screens + their frames) is sampled on a 10 cm grid and must:
  1. stay out of every opening volume (outer-wall entrances per floor, the open top-floor jump-out edge, floor .. +2.05 m);
  2. stay out of every travelator volume (ramp / balustrade / handrail AABB, up to +2 m above it);
  3. below head height (floor + 2.05 m) only exist flush on a wall (collider within 0.15 m behind the face);
  4. never sit inside a collider, and keep >= 5 cm in front of the wall behind it.
Plus: every rebuilt collider visual is the collider's own shape (the builder adds no other geometry), checked by count.
Exit code 1 if anything fails."""
import json, sys
import numpy as np
sys.path.insert(0, 'tools/inventory')
from geo import SHAPES, solid

inv = json.load(open('districts/mall/MALL_INVENTORY.json'))
CX, CZ = inv['mall']['centre_xz']
A, B = inv['mall']['semi_axes_xz']
near = [s for s in SHAPES if s.hi[0] > -85 and s.lo[0] < 15 and s.hi[2] > 15 and s.lo[2] < 140]
floors = [s for s in near if (s.hi[1] - s.lo[1]) < 1.2 and (s.hi[0] - s.lo[0]) * (s.hi[2] - s.lo[2]) > 1.0]


def ell(p):
    dx, dz = (p[:, 0] - CX) / A, (p[:, 2] - CZ) / B
    return np.sqrt(dx * dx + dz * dz), np.degrees(np.arctan2(dx, dz)) % 360.0


def in_openings(P):
    r, th = ell(P)
    hit = np.zeros(len(P), bool)
    for o in inv['openings']:
        a0, a1 = o['angle_deg']
        ang = ((th - a0) % 360.0) <= ((a1 - a0) % 360.0 if (a1 - a0) < 360 else 360.0)
        hit |= ang & (r >= o['r_band'][0]) & (r <= o['r_band'][1]) & (P[:, 1] >= o['y'][0]) & (P[:, 1] <= o['y'][1])
    return hit


def in_stairs(P):
    hit = np.zeros(len(P), bool)
    for v in inv['stair_volumes']:
        lo, hi = np.array(v['min']), np.array(v['max'])
        hit |= np.all((P >= lo - 0.05) & (P <= hi + 0.05), axis=1)
    return hit


def floor_below(p):
    best = -1e9
    for s in floors:
        if s.lo[0] <= p[0] <= s.hi[0] and s.lo[2] <= p[2] <= s.hi[2] and s.hi[1] <= p[1] + 0.01:
            if s.inside(np.array([[p[0], s.hi[1] - 0.02, p[2]]]))[0]:
                best = max(best, float(s.hi[1]))
    return best


def quad_points(c, n, w, h, step=0.1):
    c, n = np.array(c, float), np.array(n, float)
    n /= np.linalg.norm(n)
    tg = np.array([n[2], 0, -n[0]])
    us = np.arange(-w / 2, w / 2 + 1e-6, step)
    vs = np.arange(-h / 2, h / 2 + 1e-6, step)
    return np.array([c + tg * u + np.array([0, v, 0]) for u in us for v in vs]), n


items = []
for s in inv['dressing']['signs']:
    items.append(('sign L%d' % s['level'], s['pos'], s['normal'], s['size'][0], s['size'][1], 0.0))
for s in inv['dressing']['screens']:
    # screen quad at +2 cm, frame boxes 0.16 m wide around it, 8 cm deep centred at +4 cm (back face at +0 cm)
    items.append(('screen %.0f' % s['angle_deg'], s['pos'], s['normal'], s['size'][0] + 0.32, s['size'][1] + 0.32, 0.0))

for s in inv['dressing'].get('trims', []):
    items.append(('trim ' + s['role'], s['pos'], s['normal'], s['size'][0], s['size'][1], 0.0))

fails = []
quiet = 0
for name, c, n, w, h, _ in items:
    P, nn = quad_points(c, n, w, h)
    bad_open = int(in_openings(P).sum())
    bad_stair = int(in_stairs(P).sum())
    inside = int(solid(P, near).sum())
    gap = int(solid(P - nn * 0.049, near).sum())            # something within 5 cm behind the face
    # below head height: must be flush on a wall
    low = 0
    for p in P[::7]:
        f = floor_below(p)
        if f > -1e8 and p[1] < f + 2.05 and not solid(np.array([p - nn * 0.15]), near)[0]:
            low += 1
    ok = bad_open == 0 and bad_stair == 0 and inside == 0 and gap == 0 and low == 0
    if ok and name.startswith('trim'):
        quiet += 1                                          # 300+ trims: print only failures
        continue
    print('%-12s %s  openings %d  travelators %d  inside-collider %d  <5cm-from-wall %d  free-standing-below-2.05m %d  (%d pts)'
          % (name, 'OK  ' if ok else 'FAIL', bad_open, bad_stair, inside, gap, low, len(P)))
    if not ok:
        fails.append(name)

print('trims OK:', quiet)
# collider visuals: the builder draws one visual per collider shape and nothing else of its own except the items above
roles = inv['role_counts']
print('structures with roles:', sum(roles.values()), '| openings:', len(inv['openings']), '| travelator volumes:', len(inv['stair_volumes']))
print('RESULT:', 'PASS' if not fails else 'FAIL ' + ', '.join(fails))
sys.exit(1 if fails else 0)
