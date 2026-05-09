"""Quick isolation check."""
import sys
sys.path.insert(0, '.')
from map_builder import MapGenerator, MapConfig

configs = [
    (1,'none',80,60),(7,'west',80,60),(42,'east',80,60),(99,'north',80,60),(13,'south',80,60),
    (1,'none',160,120),(7,'west',160,120),(1,'none',32,32),(42,'random',128,96),
    (999,'none',80,60),(0,'none',80,60),
]
total_isolated = 0
for seed, coast, w, h in configs:
    gen = MapGenerator(MapConfig(width=w, height=h, master_seed=seed, coast_side=coast))
    gen.generate_blocking()
    road_cells = [(r,c) for r,c,cell in gen.grid.all_cells() if cell.is_road]
    visited = set()
    queue = [road_cells[0]] if road_cells else []
    if queue:
        visited.add(road_cells[0])
    while queue:
        r,c = queue.pop()
        for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
            nr,nc = r+dr, c+dc
            if gen.grid.in_bounds(nr,nc) and gen.grid[nr][nc].is_road and (nr,nc) not in visited:
                visited.add((nr,nc)); queue.append((nr,nc))
    isolated = len(road_cells) - len(visited)
    total_isolated += isolated
    land = gen.stats.get('land', 1)
    roads = gen.stats.get('roads', 0)
    rp = round(roads/land*100, 1)
    sb = sum(1 for _,_,c in gen.grid.all_cells() if c.is_setback)
    wf = sum(1 for lot in gen.lots
             if any(gen.grid.cell(r2+dr, c2+dc) is not None and gen.grid.cell(r2+dr, c2+dc).is_water
                    for r2,c2 in lot for dr,dc in ((-1,0),(1,0),(0,-1),(0,1))))
    print(f"seed={seed} coast={coast} {w}x{h}: isolated={isolated} road%={rp} sb={sb} wf_lots={wf}")
print(f"TOTAL ISOLATED: {total_isolated}")
