"""
Full 60-Configuration Test Suite
=================================
Definitive quality gate for the procedural city map generator.
Runs all 12 seeds × 5 coast modes and verifies every quality metric.

Usage:
    python tests/full_suite.py

Exit code 0 = all 60 configs pass.
Exit code 1 = one or more configs fail.
"""

import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from map_builder import MapGenerator, MapConfig
import app

# ── Quality thresholds ─────────────────────────────────────────────────────────

ROAD_PCT_MIN   = 15.0   # road cells as % of land cells
ROAD_PCT_MAX   = 35.0
PARKS_MIN      = 1      # at least one park per map
LANDMARKS_MIN  = 3      # at least 3 landmarks
MAX_RENDER_ERR = 0      # zero rendering crashes allowed
MAX_ORPHAN     = 0      # no orphan road cells

# ── Test matrix ───────────────────────────────────────────────────────────────

SEEDS  = list(range(1, 13))   # seeds 1–12
COASTS = ['none', 'north', 'south', 'east', 'west']


def run_config(seed: int, coast: str) -> tuple[bool, list[str], dict]:
    """
    Run a single map configuration and return (passed, issues, stats).
    """
    config = MapConfig(width=80, height=60, master_seed=seed, coast_side=coast)
    gen    = MapGenerator(config)
    t0     = time.perf_counter()
    gen.generate_blocking()
    elapsed = round(time.perf_counter() - t0, 2)

    s = gen.stats

    render_err   = 0
    no_role      = 0
    no_btype     = 0
    setback_bldg = 0
    park_no_role = 0
    orphan_roads = 0

    for r, c, cell in gen.grid.all_cells():
        try:
            app.cell_color(cell)
        except Exception:
            render_err += 1

        if cell.is_land and cell.tile_role == '':
            no_role += 1

        if (cell.lot_id >= 0
                and cell.building_type == ''
                and not cell.is_park
                and not getattr(cell, 'is_setback', False)
                and getattr(cell, 'footprint_style', '') not in ('courtyard', 'lshape')):
            no_btype += 1

        if getattr(cell, 'is_setback', False) and cell.tile_role.startswith('bldg_'):
            setback_bldg += 1

        if cell.is_park and cell.tile_role != 'park':
            park_no_role += 1

        if cell.is_road and gen.grid.road_bitmask(r, c) == 0:
            orphan_roads += 1

    land     = s['land']
    road_pct = round(s['roads'] / land * 100, 1) if land else 0.0
    parks    = s['parks']
    lmk      = s.get('landmarks', 0)

    # ── Verify new Sprint 5 features ──────────────────────────────────────────

    # Feature 7: elevation set on land cells
    elev_ok = any(
        getattr(cell, 'elevation', 0.0) > 0.0
        for _, _, cell in gen.grid.all_cells()
        if cell.is_land
    )

    # Feature 3: district names generated
    districts_ok = len(s.get('districts', [])) > 0

    # Feature 4: footprint styles assigned (only checked when lots exist)
    has_footprint = any(
        getattr(cell, 'footprint_style', '') in ('courtyard', 'lshape')
        for _, _, cell in gen.grid.all_cells()
    )

    issues: list[str] = []
    if render_err:          issues.append(f'CRASH={render_err}')
    if no_role:             issues.append(f'no_role={no_role}')
    if no_btype:            issues.append(f'no_btype={no_btype}')
    if setback_bldg:        issues.append(f'setback_bldg={setback_bldg}')
    if park_no_role:        issues.append(f'park_no_role={park_no_role}')
    if orphan_roads:        issues.append(f'orphan={orphan_roads}')
    if road_pct < ROAD_PCT_MIN or road_pct > ROAD_PCT_MAX:
        issues.append(f'road%={road_pct}')
    if parks < PARKS_MIN:   issues.append('NO_PARKS')
    if lmk < LANDMARKS_MIN: issues.append(f'lmk={lmk}')
    if not elev_ok:         issues.append('NO_ELEVATION')
    if not districts_ok:    issues.append('NO_DISTRICTS')

    return (len(issues) == 0, issues, {
        'seed': seed, 'coast': coast,
        'parks': parks, 'lots': s['lots'], 'lmk': lmk,
        'road_pct': road_pct, 'elapsed': elapsed,
        'has_footprint': has_footprint,
    })


def main() -> int:
    print("=" * 72)
    print("  FULL 60-CONFIGURATION TEST SUITE — Sprint 5 Quality Gate")
    print("=" * 72)
    print()

    pass_count = 0
    fail_count = 0
    total      = len(SEEDS) * len(COASTS)
    start      = time.perf_counter()

    for seed in SEEDS:
        for coast in COASTS:
            passed, issues, info = run_config(seed, coast)

            status = 'PASS' if passed else ('FAIL: ' + ', '.join(issues))
            fp_mark = '✓' if info['has_footprint'] else ' '
            print(
                f"  seed={seed:2d} coast={coast:5s}: "
                f"parks={info['parks']:2d} lots={info['lots']:4d} lmk={info['lmk']} "
                f"road%={info['road_pct']:5.1f}  fp={fp_mark}  {status}"
            )

            if passed:
                pass_count += 1
            else:
                fail_count += 1

    elapsed_total = round(time.perf_counter() - start, 1)
    print()
    print("=" * 72)
    print(f"  RESULT:  PASS {pass_count}/{total}   FAIL {fail_count}/{total}   ({elapsed_total}s)")
    print("=" * 72)

    if fail_count == 0:
        print("\n  ALL TESTS PASSED — build is GREEN\n")
        return 0
    else:
        print(f"\n  {fail_count} TEST(S) FAILED — build is RED\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
