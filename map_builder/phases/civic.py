"""
map_builder/phases/civic.py
────────────────────────────
Phase 5.5 — CBD Civic Anchor

Places a single civic anchor cell at the Chebyshev centroid of all CBD land cells.
This cell acts as the conceptual town-hall / civic-centre origin point.
It is placed after zone assignment and before highways so road layout can
optionally respond to it in future phases.

Sets cell.is_civic_anchor = True on exactly one cell.
"""
from __future__ import annotations
from typing import Generator

from ..constants import PHASE_CIVIC, ZONE_CBD
from ..map_state import MapGrid, MapConfig, GeneratorProgress


def generate_civic_anchor(
    grid:   MapGrid,
    config: MapConfig,
    sink:   list | None = None,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 5.5 generator — Civic Anchor Placement.

    Finds the land cell closest to the mean position of all CBD land cells
    and marks it as is_civic_anchor = True.
    If `sink` is provided, appends the (row, col) tuple of the anchor cell.
    """
    yield GeneratorProgress(PHASE_CIVIC, 0.0, 'Placing civic anchor …')

    cbd_cells = [
        (r, c) for r, c, cell in grid.all_cells()
        if cell.is_land and cell.zone_id == ZONE_CBD
    ]

    if not cbd_cells:
        yield GeneratorProgress(PHASE_CIVIC, 1.0, 'No CBD cells — civic anchor skipped.')
        return

    mean_r = sum(r for r, _ in cbd_cells) / len(cbd_cells)
    mean_c = sum(c for _, c in cbd_cells) / len(cbd_cells)

    best = min(
        cbd_cells,
        key=lambda rc: max(abs(rc[0] - mean_r), abs(rc[1] - mean_c)),
    )

    grid[best[0]][best[1]].is_civic_anchor = True

    if sink is not None:
        sink.append(best)

    yield GeneratorProgress(
        PHASE_CIVIC, 1.0,
        f'Civic anchor placed at row={best[0]}, col={best[1]}.',
    )
