"""
map_builder/phases/parks.py
────────────────────────────
Phase 7 — Park Placement

Converts qualifying city blocks to park cells based on zone and size:
  • CBD / Midtown : small residual blocks (< PARK_SMALL_BLOCK_MAX) become pocket parks
  • Residential   : medium blocks (PARK_RESIDENTIAL_MIN_AREA–MAX_AREA) have a
                    PARK_RESIDENTIAL_PROBABILITY chance of becoming a neighbourhood park

Sets cell.is_park = True on every cell in selected blocks.
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_PARKS, SALT_PARKS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    PARK_SMALL_BLOCK_MAX,
    PARK_RESIDENTIAL_MIN_AREA, PARK_RESIDENTIAL_MAX_AREA,
    PARK_RESIDENTIAL_PROBABILITY,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress


def generate_parks(
    grid:   MapGrid,
    config: MapConfig,
    blocks: list,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 7 generator — Park Placement.

    `blocks` is the list of interior block cell-sets produced by the blocks phase.
    Modifies grid cells in-place (sets is_park).
    """
    yield GeneratorProgress(PHASE_PARKS, 0.0, 'Placing parks …')

    rng = random.Random(config.master_seed ^ SALT_PARKS)
    park_count = 0
    total = max(len(blocks), 1)

    for i, block in enumerate(blocks):
        if not block:
            continue
        area = len(block)
        sample_r, sample_c = next(iter(block))
        zone = grid[sample_r][sample_c].zone_id
        make_park = False

        if zone in (ZONE_CBD, ZONE_MIDTOWN):
            if area < PARK_SMALL_BLOCK_MAX:
                make_park = True
        elif zone == ZONE_RESIDENTIAL:
            if PARK_RESIDENTIAL_MIN_AREA <= area <= PARK_RESIDENTIAL_MAX_AREA:
                if rng.random() < PARK_RESIDENTIAL_PROBABILITY:
                    make_park = True

        if make_park:
            for r, c in block:
                grid[r][c].is_park = True
            park_count += 1

        if i % 50 == 0:
            yield GeneratorProgress(
                PHASE_PARKS,
                i / total,
                f'Parks: {park_count} placed so far …',
            )

    yield GeneratorProgress(
        PHASE_PARKS, 1.0,
        f'Park placement complete — {park_count} parks placed.',
    )
