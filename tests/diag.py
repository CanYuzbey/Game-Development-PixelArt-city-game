"""
tests/diag.py
─────────────
Team 2 — 60-configuration diagnostic.
Runs 12 seeds × 5 coast modes and reports per-config quality signals.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder import MapGenerator, MapConfig
import app
import time

seeds  = list(range(1, 13))   # 12 seeds
coasts = ['none', 'north', 'south', 'east', 'west']
results = []
total_errors = 0

for seed in seeds:
    for coast in coasts:
        config = MapConfig(width=80, height=60, master_seed=seed, coast_side=coast)
        gen = MapGenerator(config)
        t0 = time.perf_counter()
        gen.generate_blocking()
        elapsed = round(time.perf_counter() - t0, 3)
        s = gen.stats

        cell_errors    = 0
        no_role        = 0
        no_btype       = 0
        setback_bldg   = 0
        park_no_role   = 0
        orphan_roads   = 0
        multi_zone_blocks: dict = {}

        for r, c, cell in gen.grid.all_cells():
            try:
                app.cell_color(cell)
            except Exception:
                cell_errors += 1
                total_errors += 1

            if cell.is_land and cell.tile_role == '':
                no_role += 1

            if cell.lot_id >= 0 and cell.building_type == '' and not cell.is_park and not getattr(cell, 'is_setback', False):
                # Check footprint style — courtyard/L-shape interiors are intentionally empty
                if getattr(cell, 'footprint_style', '') not in ('courtyard', 'lshape'):
                    no_btype += 1

            if getattr(cell, 'is_setback', False) and cell.tile_role.startswith('bldg_'):
                setback_bldg += 1

            if cell.is_park and cell.tile_role != 'park':
                park_no_role += 1

            if cell.is_road and gen.grid.road_bitmask(r, c) == 0:
                orphan_roads += 1

            if cell.block_id >= 0:
                if cell.block_id not in multi_zone_blocks:
                    multi_zone_blocks[cell.block_id] = set()
                multi_zone_blocks[cell.block_id].add(cell.zone_id)

        multi_zone = sum(1 for zones in multi_zone_blocks.values() if len(zones) > 1)

        land     = s['land']
        road_pct = round(s['roads'] / land * 100, 1) if land else 0

        result = {
            'seed': seed, 'coast': coast,
            'errors': cell_errors,
            'parks': s['parks'], 'lots': s['lots'],
            'landmarks': s.get('landmarks', 0),
            'road_pct': road_pct,
            'orphan_roads': orphan_roads,
            'no_role': no_role,
            'no_btype': no_btype,
            'setback_bldg': setback_bldg,
            'park_no_role': park_no_role,
            'multi_zone_blocks': multi_zone,
            'elapsed': elapsed,
        }
        results.append(result)

        issues = []
        if cell_errors:    issues.append(f'CRASH={cell_errors}')
        if no_role:        issues.append(f'no_role={no_role}')
        if no_btype:       issues.append(f'no_btype={no_btype}')
        if setback_bldg:   issues.append(f'setback_bldg={setback_bldg}')
        if park_no_role:   issues.append(f'park_no_role={park_no_role}')
        if orphan_roads:   issues.append(f'orphan={orphan_roads}')
        if multi_zone:     issues.append(f'multi_zone_blocks={multi_zone}')
        if road_pct < 15 or road_pct > 35:
            issues.append(f'road%={road_pct}')
        if s['parks'] == 0:
            issues.append('NO_PARKS')
        if s.get('landmarks', 0) < 3:
            issues.append(f'lmk={s.get("landmarks", 0)}')

        status = 'FAIL: ' + ', '.join(issues) if issues else 'ok'
        print(
            f"seed={seed:3d} coast={coast:5s}: "
            f"parks={s['parks']:2d} lots={s['lots']:4d} lmk={s.get('landmarks',0)} "
            f"road%={road_pct:5.1f} t={elapsed:.2f}s | {status}"
        )

print(f"\nTotal render errors across 60 configs: {total_errors}")

fail_count = sum(
    1 for r in results
    if r['errors'] or r['no_role'] or r['no_btype'] or r['setback_bldg']
    or r['park_no_role'] or r['orphan_roads'] or r['multi_zone_blocks']
    or r['road_pct'] < 15 or r['road_pct'] > 35
    or r['parks'] == 0 or r['landmarks'] < 3
)
print(f"PASS: {60 - fail_count}/60   FAIL: {fail_count}/60")
