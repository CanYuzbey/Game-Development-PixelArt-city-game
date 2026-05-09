"""Convergence test script for the city map generator."""
import sys
import time
sys.path.insert(0, '.')
from map_builder import MapGenerator, MapConfig

results = []
configs = [
    (1,'none',80,60),(7,'west',80,60),(42,'east',80,60),(99,'north',80,60),(13,'south',80,60),
    (1,'none',160,120),(7,'west',160,120),(1,'none',32,32),(42,'random',128,96),
    (999,'none',80,60),(0,'none',80,60),
]
for seed, coast, w, h in configs:
    t0 = time.perf_counter()
    config = MapConfig(width=w, height=h, master_seed=seed, coast_side=coast)
    gen = MapGenerator(config)
    try:
        gen.generate_blocking()
        elapsed = time.perf_counter() - t0
        errors = 0
        try:
            import app
            for r, c, cell in gen.grid.all_cells():
                try:
                    app.cell_color(cell)
                except Exception as e:
                    errors += 1
                    print(f'  CRASH seed={seed} ({r},{c}): {e}')
        except Exception as e:
            print(f'  APP IMPORT ERROR: {e}')
        s = gen.stats
        land = s.get('land', 1)
        rd = s.get('roads', 0) / land if land else 0
        wf = sum(1 for _, _, c in gen.grid.all_cells()
                 if getattr(c, 'building_type', '') in ['restaurant', 'market', 'station']
                 and c.lot_id >= 0)
        sb = sum(1 for _, _, c in gen.grid.all_cells() if getattr(c, 'is_setback', False))
        unassigned = sum(1 for _, _, c in gen.grid.all_cells()
                         if c.is_land and c.tile_role == '')
        tiny_lots = sum(1 for lot in gen.lots if len(lot) < 4)
        no_bldg = sum(1 for _, _, c in gen.grid.all_cells()
                      if c.lot_id >= 0 and not getattr(c, 'is_setback', False)
                      and getattr(c, 'building_type', '') == '')
        results.append({
            'seed': seed, 'coast': coast, 'size': f'{w}x{h}', 'errors': errors,
            'parks': s.get('parks', 0), 'lots': s.get('lots', 0),
            'blocks': s.get('blocks', 0), 'landmarks': s.get('landmarks', 0),
            'road_pct': round(rd * 100, 1), 'waterfront': wf, 'setbacks': sb,
            'time': round(elapsed, 3), 'unassigned': unassigned,
            'tiny_lots': tiny_lots, 'no_bldg': no_bldg,
        })
        print(f"seed={seed} coast={coast} {w}x{h}: "
              f"err={errors} parks={s.get('parks',0)} lots={s.get('lots',0)} "
              f"blocks={s.get('blocks',0)} lmk={s.get('landmarks',0)} "
              f"road%={round(rd*100,1)} wf={wf} sb={sb} "
              f"unassigned={unassigned} tiny_lots={tiny_lots} no_bldg={no_bldg} "
              f"t={round(elapsed,3)}s")
    except Exception as e:
        import traceback
        print(f'GENERATION CRASH seed={seed} coast={coast}: {e}')
        traceback.print_exc()

total_errors = sum(r['errors'] for r in results)
avg_parks = sum(r['parks'] for r in results) / len(results) if results else 0
avg_lots = sum(r['lots'] for r in results) / len(results) if results else 0
avg_landmarks = sum(r['landmarks'] for r in results) / len(results) if results else 0
avg_road_pct = sum(r['road_pct'] for r in results) / len(results) if results else 0
total_unassigned = sum(r['unassigned'] for r in results)
total_tiny = sum(r['tiny_lots'] for r in results)
total_no_bldg = sum(r['no_bldg'] for r in results)

print(f"\nSUMMARY:")
print(f"  total_errors={total_errors}")
print(f"  avg_parks={avg_parks:.1f} (target >= 1.5)")
print(f"  avg_lots={avg_lots:.1f} (target >= 40)")
print(f"  avg_landmarks={avg_landmarks:.1f} (target >= 3)")
print(f"  avg_road_pct={avg_road_pct:.1f}% (target 15-35%)")
print(f"  total_unassigned_cells={total_unassigned}")
print(f"  total_tiny_lots_(<4cells)={total_tiny}")
print(f"  total_lots_missing_building={total_no_bldg}")
