"""Precompute visual hull triangles for the old map's convex colliders inside one district region.
Usage: python tools/convex_hulls.py <x0> <z0> <x1> <z1> <out.json>   (run from art_pass/, needs numpy + scipy)
Output: {static_index: [i0,i1,i2, ...]} triangles into that shape's own point list (counter-clockwise outward)."""
import json, sys
import numpy as np
from scipy.spatial import ConvexHull

x0, z0, x1, z1 = map(float, sys.argv[1:5])
d = json.load(open("export/layout_dump.json"))
out = {}
for i, s in enumerate(d["static"]):
    if s["type"] != "convex":
        continue
    xf = s["xf"]
    B = np.array([xf[0:3], xf[3:6], xf[6:9]])
    p = np.array(s["points"]).reshape(-1, 3)
    w = p @ B + np.array(xf[9:12])
    lo, hi = w.min(0), w.max(0)
    if hi[0] < x0 or lo[0] > x1 or hi[2] < z0 or lo[2] > z1:
        continue
    try:
        h = ConvexHull(p)
    except Exception:
        continue
    c = p.mean(0)
    tris = []
    for f in h.simplices:
        a, b, cc = p[f]
        if np.dot(np.cross(b - a, cc - a), a - c) < 0:
            f = [f[0], f[2], f[1]]
        tris += [int(v) for v in f]
    out[str(i)] = tris
json.dump(out, open(sys.argv[5], "w"))
print(len(out), "hulls ->", sys.argv[5])
