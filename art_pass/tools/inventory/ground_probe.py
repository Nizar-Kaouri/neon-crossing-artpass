"""Ground probe over layout_dump.json (Claude, ground pass): a top-down grid per district that says, per cell,
where the old flat ground is and what stands on it or hangs over it. Used by ground_detail.py and its self-check.

Per cell (size RES m, centres at x0 + (i + 0.5) * RES):
  gtop   top y of the old ground slab (a flat box whose top is the district level, +-1 cm), -inf if none
  block  True if any OTHER collider occupies the column (gtop + 3 mm .. gtop + HEAD): walls, stairs, ramps, landings,
         kerbs, benches, building floors ... (decals never go there)
  cover  lowest bottom y of a collider above gtop + HEAD (roof, ceiling, bridge, canopy), +inf if open sky
The vertical extent of a box / convex collider over a cell centre is found exactly from its half-spaces;
concave shapes (stair flights, the shrine hill) are rasterised triangle by triangle."""
import numpy as np
from geo import S, SHAPES

RES = 0.1
HEAD = 2.2


def halfspaces(sh):
    """World half-spaces A p <= b of a box / convex shape (None for others)."""
    o, Binv = sh.o, sh.Binv
    if sh.t == 'box':
        C = Binv.T                                  # local L_k = (p - o) . Binv[:, k]
        A = np.vstack([C, -C]); h = np.concatenate([sh.h, sh.h])
        return A, h + A @ o
    if sh.t == 'convex' and sh.eq is not None:
        N = (Binv @ sh.eq[:, :3].T).T               # (p - o) . N_i + d_i <= 0
        return N, -sh.eq[:, 3] + N @ o
    return None


def column(sh, X, Z):
    """lo, hi (NaN where the vertical line misses the shape) at points X, Z (1-D arrays)."""
    n = len(X)
    lo = np.full(n, -np.inf); hi = np.full(n, np.inf); ok = np.ones(n, bool)
    if sh.t == 'cylinder':
        s = sh.s; r = s.get('radius', .5)
        cx, cz = sh.o[0], sh.o[2]
        ok = np.hypot(X - cx, Z - cz) <= r
        lo[:] = sh.lo[1]; hi[:] = sh.hi[1]
    else:
        hs = halfspaces(sh)
        if hs is None:
            return np.full(n, np.nan), np.full(n, np.nan)
        A, b = hs
        for a, bb in zip(A, b):
            r = bb - a[0] * X - a[2] * Z
            if a[1] > 1e-6:
                hi = np.minimum(hi, r / a[1])
            elif a[1] < -1e-6:
                lo = np.maximum(lo, r / a[1])
            else:
                ok &= r >= -1e-6
    ok &= lo <= hi + 1e-6
    lo[~ok] = np.nan; hi[~ok] = np.nan
    return lo, hi


class Grid:
    def __init__(self, rect, level, res=RES):
        self.x0, self.z0, self.x1, self.z1 = rect
        self.res, self.level = res, level
        self.nx = int(round((self.x1 - self.x0) / res)); self.nz = int(round((self.z1 - self.z0) / res))
        self.gtop = np.full((self.nz, self.nx), -np.inf)
        self.block = np.zeros((self.nz, self.nx), bool)
        self.cover = np.full((self.nz, self.nx), np.inf)
        self.ground_ids = set()

    def cells(self, lo, hi, pad=0.0):
        i0 = max(0, int(np.floor((lo[0] - pad - self.x0) / self.res))); i1 = min(self.nx, int(np.ceil((hi[0] + pad - self.x0) / self.res)))
        k0 = max(0, int(np.floor((lo[2] - pad - self.z0) / self.res))); k1 = min(self.nz, int(np.ceil((hi[2] + pad - self.z0) / self.res)))
        return i0, i1, k0, k1

    def centres(self, i0, i1, k0, k1):
        xs = self.x0 + (np.arange(i0, i1) + 0.5) * self.res
        zs = self.z0 + (np.arange(k0, k1) + 0.5) * self.res
        return np.meshgrid(xs, zs)

    def is_ground(self, sh):
        if sh.t != 'box' or abs(sh.hi[1] - self.level) > 0.01:
            return False
        # flat, axis-aligned slab of at least 4 m^2 and 0.2 m thick
        return abs(sh.B[1, 1]) > 0.999 and (sh.hi[1] - sh.lo[1]) >= 0.2 and (sh.hi[0] - sh.lo[0]) * (sh.hi[2] - sh.lo[2]) >= 4.0

    def build(self, shapes=SHAPES, extra_skip=()):
        mine = [sh for sh in shapes if sh.hi[0] >= self.x0 and sh.lo[0] <= self.x1 and sh.hi[2] >= self.z0 and sh.lo[2] <= self.z1
                and sh.hi[1] >= self.level - 1.0 and sh.lo[1] <= self.level + 12.0 and sh.i not in extra_skip]
        for sh in mine:                                             # pass 1: ground slabs
            if not self.is_ground(sh):
                continue
            self.ground_ids.add(sh.i)
            i0, i1, k0, k1 = self.cells(sh.lo, sh.hi)
            if i1 <= i0 or k1 <= k0:
                continue
            X, Z = self.centres(i0, i1, k0, k1)
            inside = (X >= sh.lo[0]) & (X <= sh.hi[0]) & (Z >= sh.lo[2]) & (Z <= sh.hi[2])
            g = self.gtop[k0:k1, i0:i1]
            g[inside] = np.maximum(g[inside], sh.hi[1])
        for sh in mine:                                             # pass 2: everything else
            if sh.i in self.ground_ids:
                continue
            i0, i1, k0, k1 = self.cells(sh.lo, sh.hi, pad=self.res)
            if i1 <= i0 or k1 <= k0:
                continue
            X, Z = self.centres(i0, i1, k0, k1)
            if sh.t == 'concave':
                lo, hi = self._concave(sh, X, Z)
            else:
                lo, hi = column(sh, X.ravel(), Z.ravel())
                lo = lo.reshape(X.shape); hi = hi.reshape(X.shape)
            hit = ~np.isnan(lo)
            if not hit.any():
                continue
            g = self.gtop[k0:k1, i0:i1]
            base = np.where(np.isfinite(g), g, self.level)
            occ = hit & (hi > base + 0.003) & (lo < base + HEAD)
            self.block[k0:k1, i0:i1] |= occ
            over = hit & (lo >= base + HEAD)
            c = self.cover[k0:k1, i0:i1]
            c[over] = np.minimum(c[over], lo[over])
        return self

    def _concave(self, sh, X, Z):
        f = np.array(S[sh.i]['faces']).reshape(-1, 3, 3) @ sh.B + sh.o
        lo = np.full(X.shape, np.nan); hi = np.full(X.shape, np.nan)
        x0 = X[0, 0]; z0 = Z[0, 0]
        for tri in f:
            a, b, c = tri
            i0 = max(0, int(np.floor((tri[:, 0].min() - x0) / self.res))); i1 = min(X.shape[1], int(np.ceil((tri[:, 0].max() - x0) / self.res)) + 1)
            k0 = max(0, int(np.floor((tri[:, 2].min() - z0) / self.res))); k1 = min(X.shape[0], int(np.ceil((tri[:, 2].max() - z0) / self.res)) + 1)
            if i1 <= i0 or k1 <= k0:
                continue
            px = X[k0:k1, i0:i1]; pz = Z[k0:k1, i0:i1]
            d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            if abs(d) < 1e-9:
                continue
            l1 = ((b[2] - c[2]) * (px - c[0]) + (c[0] - b[0]) * (pz - c[2])) / d
            l2 = ((c[2] - a[2]) * (px - c[0]) + (a[0] - c[0]) * (pz - c[2])) / d
            l3 = 1 - l1 - l2
            m = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
            y = l1 * a[1] + l2 * b[1] + l3 * c[1]
            L = lo[k0:k1, i0:i1]; H = hi[k0:k1, i0:i1]
            L[m] = np.fmin(L[m], y[m]); H[m] = np.fmax(H[m], y[m])
        lo = np.where(np.isnan(lo), np.nan, lo - 0.3)            # stair flights / hill: treat as solid 30 cm below the surface
        return lo, hi

    def xz(self, i, k):
        return self.x0 + (i + 0.5) * self.res, self.z0 + (k + 0.5) * self.res

    def idx(self, x, z):
        return int(np.floor((x - self.x0) / self.res)), int(np.floor((z - self.z0) / self.res))
