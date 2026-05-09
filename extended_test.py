import sys
sys.path.insert(0, '.')
from map_builder import MapGenerator, MapConfig
import app
import time

# Extended edge-case test including all spec-mentioned cases
configs = [
    (1,       'none',   80,  60,  'standard inland'),
    (7,       'west',   80,  60,  'standard west coast'),
    (42,      'east',   80,  60,  'standard east coast'),
    (99,      'north',  80,  60,  'north coast'),
    (13,      'south',  80,  60,  'south coast'),
    (1,       'none',   160, 120, 'large inland'),
    (7,       'west',   160, 120, 'large coastal'),
    (1,       'none',   32,  32,  'tiny map'),
    (42,      'random', 128, 96,  'medium random'),
    (999,     'none',   80,  60,  'high seed'),
    (0,       'none',   80,  60,  'zero seed'),
    (2147483647, 'none', 80, 60,  'max seed'),
    (12345,   'west',   64,  48,  'extra coastal'),
    (7777,    'north',  96,  72,  'extra north'),
]

print('Extended edge-case test:')
for seed, coast, w, h, desc in configs:
    t0 = time.perf_counter()
    config = MapConfig(width=w, height=h, master_seed=seed, coast_side=coast)
    gen = MapGenerator(config)
    gen.generate_blocking()
    elapsed = time.perf_counter() - t0
    errors = 0
    for r, c, cell in gen.grid.all_cells():
        try:
            app.cell_color(cell)
        except Exception as e:
            errors += 1
            print(f'  CRASH seed={seed} ({r},{c}): {e}')
    s = gen.stats
    land = s['land']
    rd = s['roads'] / land if land else 0
    iso = sum(
        1 for r2, c2, cell in gen.grid.all_cells()
        if cell.is_road and all(
            not gen.grid.in_bounds(r2 + dr, c2 + dc) or not gen.grid[r2 + dr][c2 + dc].is_road
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        )
    )
    print(f'  {desc}: err={errors} parks={s["parks"]} lots={s["lots"]} lmk={s.get("landmarks",0)} road%={rd*100:.1f} iso={iso} t={elapsed:.3f}s')
