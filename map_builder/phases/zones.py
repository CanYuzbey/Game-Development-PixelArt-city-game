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
from typing import Generator

from ..constants import (
    PHASE_ZONES,
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

    counts = grid.zone_count()
    cbd_n  = counts.get(ZONE_CBD,         0)
    mid_n  = counts.get(ZONE_MIDTOWN,     0)
    res_n  = counts.get(ZONE_RESIDENTIAL, 0)

    yield GeneratorProgress(
        PHASE_ZONES, 1.0,
        f'Zones assigned — CBD: {cbd_n}, Midtown: {mid_n}, Residential: {res_n} land cells.',
    )
