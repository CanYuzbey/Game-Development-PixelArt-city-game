import sys
sys.path.insert(0, '.')
from map_builder import MapGenerator, MapConfig
from map_builder.constants import *

config = MapConfig(width=160, height=120, master_seed=7, coast_side='west')
gen = MapGenerator(config)
gen.generate_blocking()
grid = gen.grid

lmk_cells = set()
for r, c, cell in grid.all_cells():
    if cell.landmark_type:
        lmk_cells.add(cell.landmark_type)
print(f'Landmarks placed: {lmk_cells}')
print(f'Count: {len(lmk_cells)}')

# Check highway cells in CBD/Midtown
hw_cbd_mid = [(r, c, cell.zone_id) for r, c, cell in grid.all_cells()
              if cell.is_road and cell.road_category == ROAD_HIGHWAY
              and cell.zone_id in (ZONE_CBD, ZONE_MIDTOWN)]
print(f'Highway cells in CBD/Midtown: {len(hw_cbd_mid)}')

# Find station location
from map_builder.phases.buildings import _nearest_lot_of_zone
if hw_cbd_mid:
    rows, cols = grid.height, grid.width
    cr_c, cc_c = rows / 2.0, cols / 2.0
    station_cell = min(hw_cbd_mid, key=lambda rc: (rc[0] - cr_c) ** 2 + (rc[1] - cc_c) ** 2)
    sr, sc, _ = station_cell
    nearest = _nearest_lot_of_zone(grid, sr, sc, ZONE_MIDTOWN, radius=15)
    nearest20 = _nearest_lot_of_zone(grid, sr, sc, ZONE_MIDTOWN, radius=20)
    print(f'Station cell: ({sr},{sc}), nearest(r=15): {nearest}, nearest(r=20): {nearest20}')
