"""
map_builder/phases/sidewalk.py
────────────────────────────────
Phase 4 — Sidewalk Generation

Algorithm  (rule-based edge classification):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Pass A — Mark sidewalk cells                                              │
  │   For every CONNECTOR road cell, examine each of its 4 neighbours.       │
  │   If a neighbour is land, not a road, and not water → candidate for      │
  │   sidewalk.  Mark all such neighbours.                                    │
  │   Highways are EXCLUDED — they are traffic arteries with no pedestrian   │
  │   access.                                                                 │
  │                                                                           │
  │ Pass B — Select sidewalk tile variant                                     │
  │   For each marked sidewalk cell, compute a 4-bit bitmask encoding which  │
  │   of its sides face a CONNECTOR road cell.                                │
  │   Look up the bitmask in SIDEWALK_BITMASK_TO_TILE to get the tile_id.   │
  │   Pick a variation index (seeded random) and write to LAYER_SIDEWALK.   │
  └──────────────────────────────────────────────────────────────────────────┘

Yields GeneratorProgress once per processing batch.
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_SIDEWALK,
    SALT_SIDEWALK,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    DIRECTION_OFFSETS,
    LAYER_SIDEWALK,
    TILE_SW_SURFACE,
)
from ..map_state     import MapGrid, MapConfig, GeneratorProgress
from ..tile_registry import REGISTRY


# ── Pass A: mark sidewalk cells ───────────────────────────────────────────────

def _mark_sidewalk_candidates(grid: MapGrid) -> set[tuple[int, int]]:
    """
    Return the set of (row, col) cells that should receive a sidewalk tile.
    Only land cells adjacent to CONNECTOR roads qualify.
    """
    candidates: set[tuple[int, int]] = set()

    for r, c, cell in grid.all_cells():
        if not (cell.is_road and cell.road_category == ROAD_CONNECTOR):
            continue
        for d, (dr, dc) in DIRECTION_OFFSETS.items():
            nr, nc = r + dr, c + dc
            nbr = grid.cell(nr, nc)
            if (
                nbr is not None
                and nbr.is_land
                and not nbr.is_road
                and not nbr.is_water
            ):
                candidates.add((nr, nc))

    return candidates


# ── Pass B: assign sidewalk tiles ─────────────────────────────────────────────

def _assign_sidewalk_tile(
    grid:       MapGrid,
    row:        int,
    col:        int,
    rng:        random.Random,
    damage_rate: float,
) -> None:
    """
    Compute the road-adjacency bitmask for (row, col), look up the correct
    sidewalk tile variant, and write it into LAYER_SIDEWALK.
    """
    mask    = grid.road_adjacency_bitmask(row, col)
    tile_id = REGISTRY.resolve_sidewalk_tile_id(mask)

    variants = REGISTRY.get_variants(tile_id)
    if not variants:
        # Fallback to plain surface if tile not yet calibrated
        variants = REGISTRY.get_variants(TILE_SW_SURFACE)

    if not variants:
        return

    # Prefer damaged variant at the configured rate
    damaged_variants = [v for v in variants if v.is_damaged]
    clean_variants   = [v for v in variants if not v.is_damaged]

    if damaged_variants and rng.random() < damage_rate:
        chosen_list = damaged_variants
    else:
        chosen_list = clean_variants if clean_variants else variants

    variation_idx = rng.randrange(len(chosen_list))
    grid[row][col].set_sidewalk(tile_id, variation=variation_idx)


# ── Public phase generator ────────────────────────────────────────────────────

def generate_sidewalks(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 4 generator — sidewalk placement + decoration.
    Modifies `grid` in-place.
    Yields GeneratorProgress at each significant step.
    """
    rng_sw = random.Random(config.master_seed ^ SALT_SIDEWALK)

    # ── Pass A: identify sidewalk cells ───────────────────────────────────────
    yield GeneratorProgress(PHASE_SIDEWALK, 0.0, 'Marking sidewalk candidates …')
    candidates = _mark_sidewalk_candidates(grid)

    yield GeneratorProgress(
        PHASE_SIDEWALK, 0.2,
        f'{len(candidates)} sidewalk cells identified.'
    )

    # ── Pass B: assign sidewalk tiles ─────────────────────────────────────────
    total = max(1, len(candidates))
    BATCH = max(1, total // 8)

    for i, (r, c) in enumerate(sorted(candidates)):  # sorted → deterministic
        _assign_sidewalk_tile(grid, r, c, rng_sw, config.sidewalk_damage_rate)

        if i % BATCH == 0 or i == total - 1:
            yield GeneratorProgress(
                PHASE_SIDEWALK,
                0.2 + 0.7 * (i + 1) / total,
                f'Placing sidewalk tiles … {i + 1}/{total}'
            )

    yield GeneratorProgress(PHASE_SIDEWALK, 1.0, 'Sidewalks placed.')
