"""
map_builder/phases/coastline.py
────────────────────────────────
Phase 1 — Coastline Generation

Algorithm:
  1. Build a seeded permutation table.
  2. Sample 4-octave FBM noise across the entire grid.
  3. Add a directional gradient falloff so the coast appears on the
     requested side (north / south / east / west) or nowhere ('none').
  4. Threshold combined value → land (True) / water (False).
  5. Apply 2-pass majority-vote erosion to clean up pixel noise.
  6. Write LAYER_GROUND tiles and is_land / is_water flags into MapGrid.

Yields GeneratorProgress once per row-batch (roughly 8 yields for a 64-wide map).
"""
from __future__ import annotations
from typing import Generator

from ..constants import (
    PHASE_COASTLINE,
    SALT_COAST,
    COAST_RANDOM, COAST_NONE,
    TILE_GROUND_LAND, TILE_GROUND_WATER,
)
from ..map_state   import MapGrid, MapConfig, GeneratorProgress
from ..noise_utils import build_perm_table, fbm, directional_gradient, smooth_land_grid


def generate_coastline(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 1 generator.  Modifies `grid` in-place.
    Yields GeneratorProgress so the caller can drive a loading screen.
    """

    # ── Resolve coast side ────────────────────────────────────────────────────
    import random
    rng = random.Random(config.master_seed ^ SALT_COAST)

    coast_side = config.coast_side
    if coast_side == COAST_RANDOM:
        # 50% chance of a directional coast, 50% pure inland map.
        # Each of the 4 directions is equally likely when a coast is chosen.
        if rng.random() < 0.50:
            coast_side = rng.choice(['north', 'south', 'east', 'west'])
        else:
            coast_side = COAST_NONE

    yield GeneratorProgress(
        PHASE_COASTLINE, 0.0,
        f'Generating coastline ({coast_side}) …'
    )

    rows, cols = grid.height, grid.width
    BATCH = max(1, rows // 8)   # yield every BATCH rows

    # ── Fast inland path: no water, no noise needed ───────────────────────────
    if coast_side == COAST_NONE:
        for r in range(rows):
            for c in range(cols):
                cell = grid[r][c]
                cell.is_land  = True
                cell.is_water = False
                cell.set_ground(TILE_GROUND_LAND)
            if r % BATCH == 0 or r == rows - 1:
                yield GeneratorProgress(
                    PHASE_COASTLINE,
                    (r + 1) / rows,
                    f'Inland terrain: row {r + 1}/{rows}'
                )
        yield GeneratorProgress(PHASE_COASTLINE, 1.0, 'Inland map — all land.')
        return

    # ── Build noise permutation table ─────────────────────────────────────────
    perm = build_perm_table(config.master_seed ^ SALT_COAST)

    # ── Sample noise + gradient into a raw float grid ─────────────────────────
    scale = config.coast_noise_scale
    raw: list[list[float]] = []

    for r in range(rows):
        row_vals: list[float] = []
        for c in range(cols):
            nx = (c / cols) * scale
            ny = (r / rows) * scale
            noise_val  = fbm(nx, ny, perm, octaves=4, persistence=0.5, lacunarity=2.0)
            # noise_val ∈ [-1, 1] → remap to [0, 1]
            noise_norm = (noise_val + 1.0) * 0.5

            if coast_side != COAST_NONE:
                bias = directional_gradient(r, c, rows, cols, coast_side, steepness=2.2)
                # Blend: bias pulls land toward the interior, noise adds organic variation
                combined = noise_norm * 0.55 + bias * 0.45
            else:
                combined = noise_norm  # pure noise, no coast

            row_vals.append(combined)
        raw.append(row_vals)

        if r % BATCH == 0 or r == rows - 1:
            yield GeneratorProgress(
                PHASE_COASTLINE,
                (r + 1) / rows * 0.6,    # noise sampling = first 60% of phase
                f'Coast noise: row {r + 1}/{rows}'
            )

    # ── Threshold → binary land/water ────────────────────────────────────────
    # Threshold is tuned so coast_coverage fraction of cells become water.
    # We sort all values and pick the percentile cutoff.
    flat = sorted(v for row in raw for v in row)
    cutoff_idx = int(config.coast_coverage * len(flat))
    cutoff_idx = max(0, min(cutoff_idx, len(flat) - 1))
    threshold  = flat[cutoff_idx]

    land: list[list[bool]] = [
        [raw[r][c] >= threshold for c in range(cols)]
        for r in range(rows)
    ]

    yield GeneratorProgress(PHASE_COASTLINE, 0.65, 'Smoothing coastline …')

    # ── Erosion smoothing ────────────────────────────────────────────────────
    land = smooth_land_grid(land, passes=config.coast_smoothing_passes)

    yield GeneratorProgress(PHASE_COASTLINE, 0.85, 'Writing coast to grid …')

    # ── Write to MapGrid ──────────────────────────────────────────────────────
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            if land[r][c]:
                cell.is_land  = True
                cell.is_water = False
                cell.set_ground(TILE_GROUND_LAND)
            else:
                cell.is_water = True
                cell.is_land  = False
                cell.set_ground(TILE_GROUND_WATER)

    yield GeneratorProgress(PHASE_COASTLINE, 1.0, 'Coastline complete.')
