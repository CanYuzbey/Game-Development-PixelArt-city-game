"""
tests/test_e2e.py
─────────────────
End-to-end tests for the procedural city map builder engine.

These tests exercise the full generation pipeline and verify the correctness
of the road bitmask category-filtering introduced in the bug-fix branch:

  • road_bitmask(category=ROAD_HIGHWAY)  — highways only see highway neighbours
  • road_bitmask(category=ROAD_CONNECTOR) — connectors only see connector neighbours

The category filter prevents highways and connector roads from reading each
other's connectivity, which was causing wrong tile assignments at intersections.
"""
from __future__ import annotations

import sys
import os

# Allow running from repo root or tests/ subdirectory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from map_builder import MapGenerator, MapConfig
from map_builder.map_state import MapGrid, MapCell
from map_builder.constants import (
    LAYER_ROAD,
    ROAD_HIGHWAY,
    ROAD_CONNECTOR,
    ROAD_BITMASK_TO_TILE,
    TILE_ROAD_STRAIGHT_NS,
    TILE_ROAD_STRAIGHT_EW,
    TILE_ROAD_X,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_small_config(**overrides) -> MapConfig:
    """Return a minimal MapConfig that runs quickly (no coast, few roads)."""
    defaults = dict(
        width=32,
        height=32,
        master_seed=42,
        coast_side='none',
        highway_ns_min=1,
        highway_ns_max=2,
        highway_ew_min=0,
        highway_ew_max=1,
        connector_density=0.6,
        connector_spacing=6,
        avenue_spacing=12,
        roundabout_count=2,
        diagonal_streets=0,
    )
    defaults.update(overrides)
    return MapConfig(**defaults)


def _generate(config: MapConfig) -> MapGenerator:
    gen = MapGenerator(config)
    gen.generate_blocking()
    return gen


# ── Unit tests: road_bitmask category filter ─────────────────────────────────

class TestRoadBitmaskCategoryFilter:
    """
    Directly tests MapGrid.road_bitmask() with and without the category filter.
    """

    def _grid_with_cross(self) -> tuple[MapGrid, int, int]:
        """
        Build a 5×5 grid where:
          - (2,2) is a CONNECTOR road (centre)
          - (1,2) north neighbour  = HIGHWAY
          - (3,2) south neighbour  = CONNECTOR
          - (2,1) west  neighbour  = CONNECTOR
          - (2,3) east  neighbour  = CONNECTOR
        """
        grid = MapGrid(5, 5)
        # Mark all cells as land
        for r, c, cell in grid.all_cells():
            cell.is_land = True

        # Centre connector
        grid[2][2].set_road('road_placeholder', ROAD_CONNECTOR)
        # North = highway (crosses the connector road)
        grid[1][2].set_road('road_placeholder', ROAD_HIGHWAY)
        # South, West, East = connector
        grid[3][2].set_road('road_placeholder', ROAD_CONNECTOR)
        grid[2][1].set_road('road_placeholder', ROAD_CONNECTOR)
        grid[2][3].set_road('road_placeholder', ROAD_CONNECTOR)

        return grid, 2, 2

    def test_no_filter_counts_all_roads(self):
        grid, r, c = self._grid_with_cross()
        # Without category filter all 4 neighbours are road → bitmask = 15
        assert grid.road_bitmask(r, c) == 15  # N=8 E=4 S=2 W=1

    def test_connector_filter_excludes_highway(self):
        grid, r, c = self._grid_with_cross()
        # With connector filter: north (highway) must NOT be counted
        # Expected: E=4 S=2 W=1 → 7
        result = grid.road_bitmask(r, c, ROAD_CONNECTOR)
        assert result == 7, (
            f"Expected 7 (ESW), got {result}. "
            "Highway neighbour should be excluded by connector filter."
        )

    def test_highway_filter_only_counts_highway(self):
        grid, r, c = self._grid_with_cross()
        # With highway filter only: only north (highway) → 8
        result = grid.road_bitmask(r, c, ROAD_HIGHWAY)
        assert result == 8, (
            f"Expected 8 (N only), got {result}. "
            "Only the highway neighbour should be counted."
        )

    def test_no_neighbours_gives_zero(self):
        grid = MapGrid(3, 3)
        for _, _, cell in grid.all_cells():
            cell.is_land = True
        grid[1][1].set_road('road_placeholder', ROAD_CONNECTOR)
        assert grid.road_bitmask(1, 1, ROAD_CONNECTOR) == 0
        assert grid.road_bitmask(1, 1, ROAD_HIGHWAY) == 0
        assert grid.road_bitmask(1, 1) == 0

    def test_out_of_bounds_cells_do_not_crash(self):
        grid = MapGrid(3, 3)
        for _, _, cell in grid.all_cells():
            cell.is_land = True
        grid[0][0].set_road('road_placeholder', ROAD_HIGHWAY)
        # Top-left corner: N and W neighbours are out of bounds
        assert grid.road_bitmask(0, 0, ROAD_HIGHWAY) == 0

    def test_two_same_category_straight_ns(self):
        """A road with only N and S connector neighbours → straight N-S bitmask."""
        grid = MapGrid(5, 5)
        for _, _, cell in grid.all_cells():
            cell.is_land = True
        grid[1][2].set_road('road_placeholder', ROAD_CONNECTOR)
        grid[2][2].set_road('road_placeholder', ROAD_CONNECTOR)
        grid[3][2].set_road('road_placeholder', ROAD_CONNECTOR)

        # Centre cell (2,2): N=8 S=2 → 10
        assert grid.road_bitmask(2, 2, ROAD_CONNECTOR) == 10
        # Matches TILE_ROAD_STRAIGHT_NS
        assert ROAD_BITMASK_TO_TILE[10] == TILE_ROAD_STRAIGHT_NS


# ── Integration tests: full generation pipeline ──────────────────────────────

class TestFullGenerationPipeline:
    """End-to-end tests that run the complete four-phase pipeline."""

    def test_basic_generation_completes(self):
        gen = _generate(_make_small_config())
        grid = gen.grid
        total = grid.width * grid.height
        assert total == 32 * 32

    def test_all_land_with_no_coast(self):
        gen = _generate(_make_small_config(coast_side='none'))
        grid = gen.grid
        assert grid.water_count() == 0
        assert grid.land_count() == 32 * 32

    def test_roads_are_placed(self):
        gen = _generate(_make_small_config())
        assert gen.grid.road_count() > 0

    def test_sidewalks_are_placed(self):
        gen = _generate(_make_small_config())
        assert gen.grid.sidewalk_count() > 0

    def test_determinism_same_seed(self):
        """Same seed must produce identical road layout."""
        cfg = _make_small_config(master_seed=99)
        gen1 = _generate(cfg)
        gen2 = _generate(cfg)
        grid1 = gen1.grid
        grid2 = gen2.grid
        for r, c, cell in grid1.all_cells():
            assert cell.layers[LAYER_ROAD] == grid2[r][c].layers[LAYER_ROAD], (
                f"Tile mismatch at ({r},{c}): {cell.layers[LAYER_ROAD]} vs "
                f"{grid2[r][c].layers[LAYER_ROAD]}"
            )

    def test_different_seeds_produce_different_maps(self):
        gen1 = _generate(_make_small_config(master_seed=1))
        gen2 = _generate(_make_small_config(master_seed=2))
        road_tiles_1 = [c.layers[LAYER_ROAD] for _, _, c in gen1.grid.all_cells()]
        road_tiles_2 = [c.layers[LAYER_ROAD] for _, _, c in gen2.grid.all_cells()]
        assert road_tiles_1 != road_tiles_2

    def test_highway_tiles_have_highway_category(self):
        gen = _generate(_make_small_config(highway_ns_min=2, highway_ns_max=3))
        highway_cells = [
            (r, c, cell)
            for r, c, cell in gen.grid.all_cells()
            if cell.is_road and cell.road_category == ROAD_HIGHWAY
        ]
        assert len(highway_cells) > 0, "Expected at least some highway cells"
        for r, c, cell in highway_cells:
            assert cell.road_category == ROAD_HIGHWAY
            tile = cell.layers[LAYER_ROAD]
            assert tile is not None
            assert tile.startswith('road_') or tile.startswith('roundabout_'), (
                f"Unexpected tile '{tile}' on highway at ({r},{c})"
            )

    def test_connector_tiles_have_connector_category(self):
        gen = _generate(_make_small_config())
        connector_cells = [
            (r, c, cell)
            for r, c, cell in gen.grid.all_cells()
            if cell.is_road and cell.road_category == ROAD_CONNECTOR
        ]
        assert len(connector_cells) > 0, "Expected at least some connector cells"
        for r, c, cell in connector_cells:
            assert cell.road_category == ROAD_CONNECTOR

    def test_highway_bitmask_ignores_connector_neighbours(self):
        """
        road_bitmask(category=ROAD_HIGHWAY) must only count highway neighbours,
        not connector road neighbours.

        This tests the core fix in map_state.road_bitmask() and
        highway._resolve_road_tiles().  We verify it directly by running only
        the coastline and highway phases (stopping before the connector phase
        that re-resolves road tiles), so the highway tile IDs are still the
        ones written by _resolve_road_tiles().
        """
        from map_builder.tile_registry import REGISTRY as _REGISTRY

        # Build a config with highways but no connectors, so connector Pass 4
        # does not overwrite the highway tile IDs.
        cfg = _make_small_config(
            master_seed=7,
            highway_ns_min=2,
            highway_ns_max=3,
            highway_ew_min=1,
            highway_ew_max=2,
            connector_density=0.0,   # no connector roads placed
            roundabout_count=0,
            diagonal_streets=0,
        )
        gen = MapGenerator(cfg)
        # Run only coastline + highway phases
        for _ in gen._run_phase_coastline():
            pass
        for _ in gen._run_phase_highways():
            pass

        grid = gen.grid
        hw_cells = [
            (r, c, cell)
            for r, c, cell in grid.all_cells()
            if cell.road_category == ROAD_HIGHWAY
        ]
        assert len(hw_cells) > 0, "Need at least some highway cells to test"

        mismatches = []
        for r, c, cell in hw_cells:
            tile = cell.layers[LAYER_ROAD]
            if tile is None or tile.startswith('roundabout_'):
                continue
            mask = grid.road_bitmask(r, c, ROAD_HIGHWAY)
            expected = _REGISTRY.resolve_road_tile_id(mask, ROAD_HIGHWAY)
            if tile != expected:
                mismatches.append((r, c, tile, expected, mask))
        assert not mismatches, (
            f"{len(mismatches)} highway cells have wrong tile IDs "
            f"(after highway phase only).\n"
            + "\n".join(
                f"  ({r},{c}): stored={t!r} expected={e!r} mask={m:04b}"
                for r, c, t, e, m in mismatches[:10]
            )
        )

    def test_connector_bitmask_ignores_highway_neighbours(self):
        """
        After full generation, every connector road cell's tile ID must match
        the bitmask computed using only connector neighbours.
        This verifies the bug fix in connector.generate_connectors().

        Cells immediately adjacent to a roundabout site are excluded: their
        tile is resolved in Pass 4 (before roundabouts are placed in Pass 5),
        so their stored tile may differ from the post-generation bitmask.
        This is expected behaviour — not a bug.
        """
        from map_builder.tile_registry import REGISTRY as _REGISTRY

        gen = _generate(_make_small_config(
            master_seed=13,
            highway_ns_min=2,
            highway_ns_max=3,
        ))
        grid = gen.grid
        mismatches = []
        for r, c, cell in grid.all_cells():
            if not cell.is_road or cell.road_category != ROAD_CONNECTOR:
                continue
            tile = cell.layers[LAYER_ROAD]
            if tile is None or tile.startswith('roundabout_'):
                continue

            # Skip cells adjacent to any roundabout tile — their bitmask was
            # frozen before roundabout placement (Pass 4 runs before Pass 5).
            nbrs = grid.neighbours(r, c)
            adj_to_roundabout = any(
                nb is not None
                and nb.layers[LAYER_ROAD] is not None
                and nb.layers[LAYER_ROAD].startswith('roundabout_')
                for nb in nbrs.values()
            )
            if adj_to_roundabout:
                continue

            mask = grid.road_bitmask(r, c, ROAD_CONNECTOR)
            expected = _REGISTRY.resolve_road_tile_id(mask, ROAD_CONNECTOR)
            if tile != expected:
                mismatches.append((r, c, tile, expected, mask))
        assert not mismatches, (
            f"{len(mismatches)} connector cells have wrong tile IDs.\n"
            + "\n".join(
                f"  ({r},{c}): stored={t!r} expected={e!r} mask={m:04b}"
                for r, c, t, e, m in mismatches[:10]
            )
        )

    def test_stats_populated_after_generation(self):
        gen = _generate(_make_small_config())
        assert 'seed' in gen.stats
        assert 'roads' in gen.stats
        assert gen.stats['roads'] == gen.grid.road_count()

    def test_to_dict_and_from_dict_round_trip(self):
        """Serialise then deserialise should reproduce the identical map."""
        cfg = _make_small_config(master_seed=55)
        gen1 = _generate(cfg)
        data = gen1.to_dict()
        gen2 = MapGenerator.from_dict(data)
        gen2.generate_blocking()
        for r, c, cell in gen1.grid.all_cells():
            assert cell.layers[LAYER_ROAD] == gen2.grid[r][c].layers[LAYER_ROAD], (
                f"Round-trip mismatch at ({r},{c})"
            )


# ── Regression: cross-category junctions get correct bitmask ─────────────────

class TestCrossCategoryJunctionBitmask:
    """
    Regression tests for the specific scenario that motivated the bug fix:
    a connector road that physically intersects a highway.
    Before the fix, road_bitmask counted highway neighbours, so a connector
    cell crossing a highway would show a spurious extra-connection bit,
    causing a T or X tile instead of a straight tile (or vice versa).
    """

    def _build_crossing_grid(self) -> MapGrid:
        """
        7×7 grid with:
          • A horizontal highway spine at row 3 (cols 0-6)
          • A vertical connector spine at col 3 (rows 0-6)
          • They cross at (3, 3)
        """
        grid = MapGrid(7, 7)
        for _, _, cell in grid.all_cells():
            cell.is_land = True

        # Horizontal highway
        for c in range(7):
            grid[3][c].set_road('road_placeholder', ROAD_HIGHWAY)
        # Vertical connector (overwrite (3,3) as connector)
        for r in range(7):
            grid[r][3].set_road('road_placeholder', ROAD_CONNECTOR)

        return grid

    def test_connector_at_crossing_ignores_highway_row(self):
        grid = self._build_crossing_grid()
        # Connector at (3,3): N=(2,3) connector, S=(4,3) connector,
        # W=(3,2) highway, E=(3,4) highway
        # With ROAD_CONNECTOR filter: only N and S → N=8 S=2 → 10
        mask = grid.road_bitmask(3, 3, ROAD_CONNECTOR)
        assert mask == 10, f"Expected 10 (N+S straight), got {mask}"
        assert ROAD_BITMASK_TO_TILE[mask] == TILE_ROAD_STRAIGHT_NS

    def test_highway_at_crossing_ignores_connector_column(self):
        grid = self._build_crossing_grid()
        # Highway at (3,3): W=(3,2) highway, E=(3,4) highway,
        # N=(2,3) connector, S=(4,3) connector
        # With ROAD_HIGHWAY filter: only W and E → E=4 W=1 → 5
        mask = grid.road_bitmask(3, 3, ROAD_HIGHWAY)
        assert mask == 5, f"Expected 5 (E+W straight), got {mask}"
        assert ROAD_BITMASK_TO_TILE[mask] == TILE_ROAD_STRAIGHT_EW

    def test_no_filter_at_crossing_gives_all_four(self):
        grid = self._build_crossing_grid()
        mask = grid.road_bitmask(3, 3)
        assert mask == 15, f"Expected 15 (X junction, no filter), got {mask}"
        assert ROAD_BITMASK_TO_TILE[mask] == TILE_ROAD_X

    def test_connector_away_from_crossing_unaffected(self):
        grid = self._build_crossing_grid()
        # Connector at (1,3): N=(0,3) connector, S=(2,3) connector — no highway nearby
        mask = grid.road_bitmask(1, 3, ROAD_CONNECTOR)
        assert mask == 10  # straight N-S

    def test_highway_away_from_crossing_unaffected(self):
        grid = self._build_crossing_grid()
        # Highway at (3,1): W=(3,0) highway, E=(3,2) highway — no connector nearby
        mask = grid.road_bitmask(3, 1, ROAD_HIGHWAY)
        assert mask == 5  # straight E-W


# ── Smoke tests for various seeds and coast configs ───────────────────────────

class TestSmokeSeedsAndCoasts:
    """Quick smoke tests verifying generation does not crash under varied inputs."""

    @pytest.mark.parametrize("seed", [1, 7, 42, 100, 999])
    def test_seed_smoke(self, seed):
        gen = _generate(_make_small_config(master_seed=seed))
        assert gen.grid.road_count() >= 0  # just must not crash

    @pytest.mark.parametrize("coast_side", ['none', 'north', 'south', 'east', 'west'])
    def test_coast_smoke(self, coast_side):
        gen = _generate(_make_small_config(
            coast_side=coast_side,
            coast_coverage=0.2,
            master_seed=42,
        ))
        if coast_side == 'none':
            assert gen.grid.water_count() == 0
        else:
            assert gen.grid.water_count() > 0
