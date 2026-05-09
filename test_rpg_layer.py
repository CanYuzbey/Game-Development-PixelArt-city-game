"""
Team 5 Test Report — RPG Data Layer
Validates all new functionality added in Sprint 2.
"""
from __future__ import annotations
from collections import Counter
from map_builder import MapGenerator, MapConfig
from map_builder.constants import COAST_RANDOM

CFG_KWARGS = dict(
    coast_side=COAST_RANDOM, coast_coverage=0.3,
    highway_ns_max=5, highway_ew_max=3,
    connector_density=0.85, connector_spacing=6, avenue_spacing=15,
    roundabout_count=15, diagonal_streets=2,
)

def make_gen(seed: int = 1, w: int = 96, h: int = 72) -> MapGenerator:
    cfg = MapConfig(width=w, height=h, master_seed=seed, **CFG_KWARGS)
    g = MapGenerator(cfg)
    g.generate_blocking()
    return g


def run_tests():
    print("=== TEAM 5 RPG LAYER TEST REPORT ===\n")

    # ── Test 1: Determinism ──────────────────────────────────────────────────
    print("[TEST 1] Determinism — seed 1 run twice identical")
    g1 = make_gen(1)
    g2 = make_gen(1)
    r1 = Counter(cell.tile_role for _, _, cell in g1.grid.all_cells())
    r2 = Counter(cell.tile_role for _, _, cell in g2.grid.all_cells())
    assert r1 == r2, "FAIL: non-deterministic output"
    print("  PASS\n")

    g = g1

    # ── Test 2: All cells have a tile_role ───────────────────────────────────
    print("[TEST 2] All cells have a tile_role assigned")
    empty = sum(1 for _, _, cell in g.grid.all_cells() if not cell.tile_role)
    assert empty == 0, f"FAIL: {empty} cells without tile_role"
    print(f"  PASS (0 unclassified cells)\n")

    # ── Test 3: Parks visible ────────────────────────────────────────────────
    print("[TEST 3] Parks render as 'park' tile_role")
    park_cells = sum(1 for _, _, cell in g.grid.all_cells() if cell.tile_role == 'park')
    print(f"  Park role cells: {park_cells}")
    assert park_cells > 0, "FAIL: no park cells"
    print("  PASS\n")

    # ── Test 4: Buildings in all three zones ─────────────────────────────────
    print("[TEST 4] Buildings in all zones")
    for role in ('bldg_cbd', 'bldg_mid', 'bldg_resi'):
        cnt = sum(1 for _, _, cell in g.grid.all_cells() if cell.tile_role == role)
        print(f"  {role}: {cnt}")
        assert cnt > 0, f"FAIL: no {role} cells"
    print("  PASS\n")

    # ── Test 5: Landmarks placed ─────────────────────────────────────────────
    print("[TEST 5] Landmark placement")
    lm = Counter(cell.landmark_type for _, _, cell in g.grid.all_cells() if cell.landmark_type)
    print(f"  Landmarks: {dict(lm)}")
    assert len(lm) >= 1, "FAIL: no landmarks placed"
    print("  PASS\n")

    # ── Test 6: Encounter chance range ───────────────────────────────────────
    print("[TEST 6] Encounter chance in [0.0, 1.0]")
    bad = [(r, c, cell.encounter_chance)
           for r, c, cell in g.grid.all_cells()
           if not (0.0 <= cell.encounter_chance <= 1.0)]
    assert not bad, f"FAIL: {len(bad)} cells out of range"
    non_zero = sum(1 for _, _, cell in g.grid.all_cells() if cell.encounter_chance > 0)
    enc_vals = [cell.encounter_chance for _, _, cell in g.grid.all_cells() if cell.encounter_chance > 0]
    print(f"  Non-zero encounter cells: {non_zero}")
    print(f"  Range: {min(enc_vals):.3f} – {max(enc_vals):.3f}")
    print("  PASS\n")

    # ── Test 7: Spawn points ─────────────────────────────────────────────────
    print("[TEST 7] Spawn points placed")
    spawns = sum(1 for _, _, cell in g.grid.all_cells() if cell.is_spawn_point)
    print(f"  Spawn points: {spawns}")
    assert spawns > 0, "FAIL: no spawn points"
    print("  PASS\n")

    # ── Test 8: Walkability ratio 15–50% ────────────────────────────────────
    print("[TEST 8] Walkability ratio (15–50%)")
    walkable_roles = {'road', 'highway', 'alley', 'sidewalk', 'park', 'plaza'}
    walkable = sum(1 for _, _, cell in g.grid.all_cells() if cell.tile_role in walkable_roles)
    total = g.grid.width * g.grid.height
    ratio = walkable / total * 100
    print(f"  Walkable: {walkable}/{total} = {ratio:.1f}%")
    assert 15 <= ratio <= 50, f"FAIL: ratio {ratio:.1f}% out of range"
    print("  PASS\n")

    # ── Test 9: Alley encounter > road encounter ──────────────────────────────
    print("[TEST 9] Alley encounter > road encounter (danger hierarchy)")
    alley_enc = [cell.encounter_chance for _, _, cell in g.grid.all_cells()
                 if cell.tile_role == 'alley' and cell.encounter_chance > 0]
    road_enc  = [cell.encounter_chance for _, _, cell in g.grid.all_cells()
                 if cell.tile_role == 'road' and cell.encounter_chance > 0]
    if alley_enc and road_enc:
        avg_alley = sum(alley_enc) / len(alley_enc)
        avg_road  = sum(road_enc) / len(road_enc)
        print(f"  Avg alley encounter: {avg_alley:.3f}")
        print(f"  Avg road encounter:  {avg_road:.3f}")
        assert avg_alley > avg_road, "FAIL: alleys not more dangerous than roads"
    else:
        print("  SKIP: insufficient alley or road cells")
    print("  PASS\n")

    # ── Test 10: Building type assigned to lot cells ──────────────────────────
    print("[TEST 10] Building types assigned")
    bldg_typed = sum(1 for _, _, cell in g.grid.all_cells()
                     if cell.tile_role.startswith('bldg_') and cell.building_type)
    bldg_total = sum(1 for _, _, cell in g.grid.all_cells()
                     if cell.tile_role.startswith('bldg_'))
    print(f"  Buildings with type: {bldg_typed}/{bldg_total}")
    assert bldg_typed > 0, "FAIL: no building types assigned"
    print("  PASS\n")

    # ── Full role distribution ───────────────────────────────────────────────
    print("-- Role Distribution --")
    roles = Counter(cell.tile_role for _, _, cell in g.grid.all_cells())
    for role, cnt in sorted(roles.items(), key=lambda x: -x[1]):
        print(f"  {role:22s}: {cnt:6d}")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == '__main__':
    run_tests()
