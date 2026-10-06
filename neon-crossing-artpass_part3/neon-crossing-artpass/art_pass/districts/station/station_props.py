"""STATION district: inventory + dressing list from layout_dump.json (Claude, cloud).
Run from art_pass/:  python districts/station/station_props.py
Writes districts/station/STATION_INVENTORY.json and districts/station/old_convex_hulls.json.
Layout (old lab map): viaduct (deck y 11, 4 rails, columns every ~24 m) with the lethal express on the EAST track
(x -79, AnimatableBody, game code); a 2 m side platform (x -93..-91, y 11) with two shelters; a raised mid platform /
concourse (y 5.5) west of the viaduct, reached by stairs from the street; two ground-level information islands under
the viaduct (2 rooms each, doors on all four sides); two stair wells down to the underground corridor."""
import sys
sys.path.insert(0, 'districts/station')
from dresslib import *          # noqa: F401,F403
import numpy as np

RECT = (-120, -90, -72, 180)
OUT = 'districts/station/STATION_INVENTORY.json'

ROLE_IDS = {
    'viaduct_deck': [876],
    'platform': [877, 878],                              # side platform, west of the tracks (y 11)
    'track_rail': [896, 897, 898, 899],                  # x -88/-84 west track (no train), -81/-77 east track (EXPRESS)
    'viaduct_column': list(range(882, 896)),
    'raised_platform': [879],                            # mid platform / concourse y 5.5
    'raised_platform_roof': [880],
    'track_canopy_roof': [881],                          # walkable roof over the tracks, stair 913 from the deck
    'shelter_wall': [1880, 1882], 'shelter_roof': [1879, 1881],
    'canopy_post': list(range(10319, 10327)),
    'stair_flight': [907, 900, 910, 913, 1815, 1818],
    'stair_flight_ramp': [904],                          # diagonal flight whose foot lies ON landing 903: drawn steps +
                                                         # cheek walls would stand on that landing (self-check) -> ramp
    'stair_landing': [908, 909, 912, 903, 906, 901, 902, 905, 911, 914, 915, 1816, 1819],
    'info_island_roof': [1862, 1878],
    'platform_bench': list(range(4016, 4022)),
    'map_boundary': [1844, 1845, 1846],                  # > 30 m tall: the builder never draws them
}
for i in range(1847, 1879):
    if i in (1862, 1878):
        continue
    ROLE_IDS.setdefault('info_island_lintel' if BY_I[i].lo[1] > 2.0 else 'info_island_wall', []).append(i)
for i in range(3968, 4016):
    sh = BY_I[i]
    ROLE_IDS.setdefault('island_bench' if (sh.hi[0] - sh.lo[0]) > 2.0 else 'island_table', []).append(i)

structures = []
for role, ids in ROLE_IDS.items():
    for i in ids:
        e = entry(i, role)
        if role in ('stair_flight', 'stair_flight_ramp'):
            e.update(stair_axis(i))
        structures.append(e)
known = {s['dump_index'] for s in structures}
for sh in SHAPES:                                         # everything else in the region: ground slabs / underground
    cx, cz = (sh.lo[0] + sh.hi[0]) / 2, (sh.lo[2] + sh.hi[2]) / 2
    if sh.i in known or not (RECT[0] <= cx < RECT[2] and RECT[1] <= cz < RECT[3]):
        continue
    if is_slab(sh):
        role = 'ground' if sh.hi[1] > -0.5 else 'foundation'
    elif sh.hi[1] < -0.5:
        role = 'underground (see districts/underground)'
    else:
        role = 'other'
    structures.append(entry(sh.i, role))

# ------------------------------------------------------------------ the two information islands (as buildings)
def island(bid, z0, z1, kind, name):
    zc, zg = (z0 + z1) / 2, None
    # outer wall faces: x -92.18 .. -72.82, z z0-0.18 .. z1+0.18; doors 3.2 m wide, lintel at 2.7 m
    zg = zc
    door = lambda c, plane, axis: {'centre_xyz': ([c, 1.35, plane] if axis == 'x' else [plane, 1.35, c]), 'width_m': 3.2, 'height_m': 2.7, 'sill_y': 0.0}
    return {'id': bid, 'kind': kind, 'name': name,
            'footprint': {'centre_xz': [-82.5, zc], 'width_m': 19.36, 'depth_m': round(z1 - z0 + 0.36, 2)},
            'roof': {'roof_y': 4.1},
            'street_facing_sides': [
                {'normal_xz': [0, -1], 'street': True, 'openings': [door(-83.0, z0 - 0.18, 'x')]},
                {'normal_xz': [0, 1], 'street': True, 'openings': [door(-83.0, z1 + 0.18, 'x')]},
                {'normal_xz': [-1, 0], 'street': True, 'openings': [door(zg, -92.18, 'z')]},
                {'normal_xz': [1, 0], 'street': True, 'openings': [door(zg, -72.82, 'z')]}],
            'dump_shapes': [i for i in range(1847, 1879) if z0 - 0.5 <= (BY_I[i].lo[2] + BY_I[i].hi[2]) / 2 <= z1 + 0.5]}

buildings = [island('S01', -30.0, -6.0, 'konbini', 'Information island north (ticket kiosk)'),
             island('S02', 12.0, 36.0, 'info_centre', 'Information island south')]
# both have a partition at the middle z with a 4 m door; viaduct columns stand inside them (z -21..-19, 27..29)

# ------------------------------------------------------------------ dressing (visual only, all above head or flush)
props, lights, district_lights = [], [], []
cols = [i for i in ROLE_IDS['viaduct_column']]
for i in cols:
    sh = BY_I[i]
    zc = (sh.lo[2] + sh.hi[2]) / 2
    inside_island = any(z0 - 0.3 <= zc <= z1 + 0.3 for z0, z1 in ((-30, -6), (12, 36)))
    if inside_island:
        continue
    outer = (-1, 0) if sh.lo[0] < -85 else (1, 0)              # face away from the viaduct centre line
    x_face = sh.lo[0] if outer[0] < 0 else sh.hi[0]
    props.append(wall_mount('P_wall_lamp', x_face, 3.4, zc, outer, why='viaduct column lamp, 3.4 m'))
    inner = (-outer[0], 0)
    x_in = sh.hi[0] if outer[0] < 0 else sh.lo[0]
    props.append(wall_mount('P_wall_lamp', x_in, 3.4, zc, inner, why='viaduct column lamp, 3.4 m (under the deck)'))
    lights.append({'position': [x_face + outer[0] * 0.4, 3.2, zc], 'kind': 'column lamp'})

# paper lanterns under the raised-platform roof (bottom y 8.7, floor 5.5 -> lantern bottom 8.07 = 2.57 m clear)
for x in (-99.0, -94.0):
    for z in np.arange(-25.0, 15.0, 7.5):
        props.append(prop('P_lantern_paper', [x, 8.7, float(z)], why='hangs from roof 880'))
for z in (-20.0, 0.0):
    lights.append({'position': [-96.5, 6.9, z], 'kind': 'raised platform lantern glow'})

# paper lanterns under the track canopy roof (bottom 13.9) over the WEST track only (the express runs at x -79,
# top 13.83: nothing hangs over x > -82.5). Deck y 11 -> lantern bottom 13.27 = 2.27 m clear.
for z in np.arange(-60.0, -28.0, 7.5):
    props.append(prop('P_lantern_paper', [-86.0, 13.9, float(z)], why='hangs from canopy roof 881, west track'))
    district_lights.append({'p': [-86.0, 13.0, float(z)], 'col': 'ffc27a', 'e': 1.4, 'r': 7.0})

# lit station signs on the two shelter back walls (face x -92.25, facing the tracks), bottom 13.1 = 2.1 m over platform
for zc in (-55.0, 40.0):
    props.append(wall_piece('M_sign_lightbox_2m', (-92.25, zc), (1, 0), 2.0, 13.1, 0.03, 0.52, depth_back=0.22, cell=2,
                            why='station name light box on shelter wall'))
    district_lights.append({'p': [-91.5, 13.4, zc], 'col': 'ffd2a0', 'e': 1.2, 'r': 6.0})
# hanging name boards under the canopy roof at both ends of the west track (bottom 13.33)
for zc, n in ((-62.6, (0, -1)), (-27.4, (0, 1))):
    props.append(wall_piece('A_sign_horizontal_2m', (-86.0, zc), n, 2.0, 13.33, 0.0, 0.55, depth_back=0.1, cell=5,
                            why='hanging name board under canopy roof'))

# express warning line: dashed yellow ribs on the deck just west of the express track (x -82.9..-82.6), 1 m every 3 m
for z in np.arange(-71.0, 73.0, 3.0):
    zz = float(z)
    if -26.5 <= zz - 0.5 <= -9.7:                          # leave stair 913 (x -84.5..-81.5) and its landing clear
        continue
    props.append(prop('G_tactile_ribs_1m', [-82.9, 11.005, zz], 0.0, why='express track warning line (deck)'))

# underground signs on the columns at the stair wells (above the pit, never over a walking surface)
props.append(wall_piece('M_sign_lightbox_2m', (-76.7, -66.0), (-1, 0), 2.0, 2.3, 0.03, 0.52, depth_back=0.22, cell=6,
                        why='"to underground / mall" sign facing the north stair well'))
props.append(wall_piece('M_sign_lightbox_2m', (-89.3, 52.0), (1, 0), 2.0, 2.3, 0.03, 0.52, depth_back=0.22, cell=6,
                        why='"to underground / mall" sign facing the south stair well'))

# tactile dot rows at the street foot of the two street stairs (just outside the landing, flush on the ground)
# (rot 90: a 1 m piece spans x pos-1..pos, z pos-0.3..pos)
for x0, z in ((-102.75, -77.2), (-98.75, 65.5)):
    for k in range(4):
        props.append(prop('G_tactile_dots_1m', [x0 + k * 0.875, 0.005, z], 90.0, why='stair foot warning dots'))

inv = {'schema_version': 1, 'district': 'station', 'source': 'layout_dump.json (Claude, cloud: districts/station/station_props.py)',
       'region': {'x': [RECT[0], RECT[2]], 'z': [RECT[1], RECT[3]]},
       'buildings': buildings, 'structures': structures, 'props': props,
       'lights_in_or_affecting_region': lights,
       'district_lights': district_lights,
       'express': {'actor': 'Gameplay/StationExpress2/ExpressCollision', 'track_x': -79.0, 'cars': 3, 'car_size': [2.8, 2.6, 12.0],
                   'body_y': [11.23, 13.83], 'note': 'moving AnimatableBody (station_train.gd); its visual is game-side, see BUILDER_REQUESTS.md'},
       'known_limits': 'buildings = the 2 info islands only (doors measured from the wall gaps); district_lights need builder request R2'}
save(inv, OUT)
hulls((-121, -91, -71, 181), 'districts/station/old_convex_hulls.json')
print(len(structures), 'structures,', len(props), 'props,', len(lights), 'lights,', len(district_lights), 'district lights')
