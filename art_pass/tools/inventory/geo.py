"""Geometry helpers over layout_dump.json: world points, AABBs, point-inside tests."""
import json, numpy as np
from scipy.spatial import ConvexHull
D = json.load(open('export/layout_dump.json'))
S = D['static']

def basis(s):
    xf = s['xf']; return np.array([xf[0:3], xf[3:6], xf[6:9]]), np.array(xf[9:12])

def local_pts(s):
    t = s['type']
    if t == 'box':
        h = np.array(s['size']) / 2
        return np.array([[a, b, c] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]) * h
    if t == 'convex': return np.array(s['points']).reshape(-1, 3)
    if t == 'concave': return np.array(s['faces']).reshape(-1, 3)
    r = s.get('radius', .5); hh = s.get('height', 1) / 2
    return np.array([[a * r, b * hh, c * r] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])

class Shape:
    def __init__(self, i, s):
        self.i, self.s, self.t = i, s, s['type']
        self.B, self.o = basis(s)
        lp = local_pts(s)
        w = lp @ self.B + self.o
        self.lo, self.hi = w.min(0), w.max(0)
        self.Binv = np.linalg.inv(self.B)
        if self.t == 'convex':
            try: self.eq = ConvexHull(lp).equations
            except Exception: self.eq = None
        if self.t == 'box': self.h = np.array(s['size']) / 2
    def inside(self, P, pad=0.0):
        P = np.atleast_2d(P)
        m = np.all((P >= self.lo - pad) & (P <= self.hi + pad), axis=1)
        if not m.any(): return m
        L = (P - self.o) @ self.Binv
        if self.t == 'box':
            return m & np.all(np.abs(L) <= self.h + pad, axis=1)
        if self.t == 'convex' and self.eq is not None:
            return m & np.all(L @ self.eq[:, :3].T + self.eq[:, 3] <= pad, axis=1)
        if self.t == 'cylinder':
            r = self.s.get('radius', .5); hh = self.s.get('height', 1) / 2
            return m & (np.hypot(L[:, 0], L[:, 2]) <= r + pad) & (np.abs(L[:, 1]) <= hh + pad)
        return m  # concave: AABB only

SHAPES = [Shape(i, s) for i, s in enumerate(S) if s['type'] in ('box', 'convex', 'concave', 'cylinder')]

def in_rect(sh, r):
    x0, z0, x1, z1 = r
    return sh.hi[0] >= x0 and sh.lo[0] <= x1 and sh.hi[2] >= z0 and sh.lo[2] <= z1

def solid(P, shapes, pad=0.0):
    P = np.atleast_2d(P); out = np.zeros(len(P), bool)
    for sh in shapes: out |= sh.inside(P, pad)
    return out
