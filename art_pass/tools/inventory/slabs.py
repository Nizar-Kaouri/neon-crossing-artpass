import sys, numpy as np
from geo import SHAPES, in_rect
def slabs(rect):
    c = []
    for sh in SHAPES:
        if sh.t != 'box' or not in_rect(sh, rect): continue
        dx, dy, dz = sh.hi - sh.lo
        cx, cz = (sh.lo[0] + sh.hi[0]) / 2, (sh.lo[2] + sh.hi[2]) / 2
        if not (rect[0] <= cx <= rect[2] and rect[1] <= cz <= rect[3]): continue
        if sh.hi[1] < 3.0 or dx < 3 or dz < 3 or dx * dz < 25 or max(dx, dz) > 120: continue
        c.append(sh)
    # cluster: overlap of footprints >= 40 % of the smaller one
    groups = []
    for sh in sorted(c, key=lambda s: -(s.hi[0]-s.lo[0])*(s.hi[2]-s.lo[2])):
        a = (sh.hi[0]-sh.lo[0])*(sh.hi[2]-sh.lo[2])
        for g in groups:
            ox = min(g['hi'][0], sh.hi[0]) - max(g['lo'][0], sh.lo[0]); oz = min(g['hi'][2], sh.hi[2]) - max(g['lo'][2], sh.lo[2])
            if ox > 0 and oz > 0 and ox * oz >= 0.4 * a:
                g['m'].append(sh); g['lo'] = np.minimum(g['lo'], sh.lo); g['hi'] = np.maximum(g['hi'], sh.hi); break
        else:
            groups.append({'m': [sh], 'lo': sh.lo.copy(), 'hi': sh.hi.copy()})
    return groups
if __name__ == '__main__':
    r = list(map(float, sys.argv[1:5]))
    for g in slabs(r):
        print(np.round(g['lo'][[0,2]],1).tolist(), np.round(g['hi'][[0,2]],1).tolist(), 'top', round(g['hi'][1],1), 'n', len(g['m']), [m.s['path'].split('/')[-1][:18] for m in g['m'][:3]])
