"""
map_builder/phases/zones.py
────────────────────────────
Phase 1.5 — City Zone Assignment

Assigns every land cell a zone_id based on its Chebyshev distance from
the effective city centre.  For coastal maps the centre is shifted inland
so the denser CBD zone falls where the city actually develops.

  ZONE_CBD         (0) : inner ~35% — dense grid, tall buildings
  ZONE_MIDTOWN     (1) : middle ~30% — mixed use
  ZONE_RESIDENTIAL (2) : outer ~35% — sparse roads, cul-de-sacs, low-rise

Runs AFTER coastline (so water cells are known) and BEFORE highway (so
highway placement can optionally read zone data).
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_ZONES, SALT_BLOCKS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    COAST_WEST, COAST_EAST, COAST_NORTH, COAST_SOUTH,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress


def generate_zones(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 1.5 generator — Zone Assignment.
    Tags every cell with a zone_id in-place.  Yields GeneratorProgress.
    """
    yield GeneratorProgress(PHASE_ZONES, 0.0, 'Assigning city zones …')

    rows, cols = grid.height, grid.width

    # Shift the effective city centre away from the coastline so the CBD
    # sits where the land actually is, not at the geometric map centre.
    center_r = rows / 2.0
    center_c = cols / 2.0
    coast = config.coast_side
    if coast == COAST_WEST:
        center_c = cols * 0.60
    elif coast == COAST_EAST:
        center_c = cols * 0.40
    elif coast == COAST_NORTH:
        center_r = rows * 0.60
    elif coast == COAST_SOUTH:
        center_r = rows * 0.40

    half_r = rows / 2.0
    half_c = cols / 2.0

    for r, c, cell in grid.all_cells():
        dr   = abs(r - center_r) / half_r
        dc   = abs(c - center_c) / half_c
        dist = max(dr, dc)          # Chebyshev: 0 = centre, 1 = corner

        if dist < 0.35:
            cell.zone_id = ZONE_CBD
        elif dist < 0.65:
            cell.zone_id = ZONE_MIDTOWN
        else:
            cell.zone_id = ZONE_RESIDENTIAL

    # ── Softening pass: noise-based boundary blending ─────────────────────────
    # Boundary cells flip zone_id with seeded probability, creating organic
    # 1–2 cell wide transition strips instead of hard geometric edges.
    rng = random.Random(config.master_seed ^ 0xBEEF)

    # Two passes: CBD→Midtown boundary (40%), then Midtown→Residential (35%)
    boundary_rules = [
        (ZONE_CBD,     ZONE_MIDTOWN,     0.40),
        (ZONE_MIDTOWN, ZONE_RESIDENTIAL, 0.35),
    ]
    for source_zone, target_zone, flip_prob in boundary_rules:
        for r, c, cell in grid.all_cells():
            if not cell.is_land:
                continue
            if cell.zone_id != source_zone:
                continue
            if cell.is_civic_anchor:
                continue
            # Check if any 4-neighbour belongs to target_zone
            has_target_neighbour = any(
                grid.cell(r + dr, c + dc) is not None
                and grid.cell(r + dr, c + dc).zone_id == target_zone
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            if has_target_neighbour and rng.random() < flip_prob:
                cell.zone_id = target_zone

    counts = grid.zone_count()
    cbd_n  = counts.get(ZONE_CBD,         0)
    mid_n  = counts.get(ZONE_MIDTOWN,     0)
    res_n  = counts.get(ZONE_RESIDENTIAL, 0)

    yield GeneratorProgress(
        PHASE_ZONES, 1.0,
        f'Zones assigned (softened) — CBD: {cbd_n}, Midtown: {mid_n}, Residential: {res_n} land cells.',
    )
