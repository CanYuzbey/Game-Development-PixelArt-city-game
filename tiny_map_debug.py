import sys
sys.path.insert(0, '.')
from map_builder import MapGenerator, MapConfig
from map_builder.constants import *

configs = [
    (1, 'none', 80, 60),
    (7, 'west', 80, 60),
    (42, 'east', 80, 60),
    (99, 'north', 80, 60),
    (13, 'south', 80, 60),
    (2147483647, 'none', 80, 60),
    (1, 'none', 32, 32),
]

all_pass = True
for seed, coast, w, h in configs:
    config = MapConfig(width=w, height=h, master_seed=seed, coast_side=coast)
    gen = MapGenerator(config)
    gen.generate_blocking()
    grid = gen.grid

    # Tiny parks
    park_sizes = {}
    for r, c, cell in grid.all_cells():
        if cell.is_park:
            bid = cell.block_id
            park_sizes[bid] = park_sizes.get(bid, 0) + 1
    tiny_parks = sum(1 for sz in park_sizes.values() if sz < 3)

    # Missing building types
    no_bldg = sum(
        1 for r, c, cell in grid.all_cells()
        if cell.lot_id >= 0 and not getattr(cell, 'is_setback', False)
        and not cell.is_park and not cell.building_type
    )

    # Empty tile roles
    empty_role = sum(1 for r, c, cell in grid.all_cells() if cell.is_land and cell.tile_role == '')

    # Setback cells with building roles
    setback_bldg = sum(
        1 for r, c, cell in grid.all_cells()
        if getattr(cell, 'is_setback', False)
        and cell.tile_role in (ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN, ROLE_BUILDING_RESI)
    )

    issues = []
    if tiny_parks > 0:
        issues.append(f'tiny_parks={tiny_parks}')
    if no_bldg > 0:
        issues.append(f'no_bldg_lots={no_bldg}')
    if empty_role > 0:
        issues.append(f'empty_role={empty_role}')
    if setback_bldg > 0:
        issues.append(f'setback_has_bldg_role={setback_bldg}')

    lmk = gen.stats.get('landmarks', 0)
    if issues:
        print(f'FAIL seed={seed} coast={coast} {w}x{h}: {issues} lmk={lmk}')
        all_pass = False
    else:
        print(f'PASS seed={seed} coast={coast} {w}x{h}: lmk={lmk}')

print()
if all_pass:
    print('All Team 5 quality checks PASS')
else:
    print('SOME CHECKS FAILED')
