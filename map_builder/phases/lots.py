"""
map_builder/phases/lots.py
───────────────────────────
Phase 8 — Lot Subdivision

Recursively splits each non-park interior block into building lots using
alternating-axis binary splitting (similar to a k-d tree), with a ±20% noise
offset on the split position to produce naturally varied lot sizes.

Sets cell.lot_id ≥ 0 on every land cell inside a subdivided lot.
Park cells and exterior cells retain lot_id == -1.
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import PHASE_LOTS, SALT_LOTS, LOT_MIN_WIDTH, LOT_MIN_DEPTH
from ..map_state import MapGrid, MapConfig, GeneratorProgress


def _subdivide_block(
    block_cells: set,
    rng: random.Random,
    lot_id_counter: list,
    min_w: int,
    min_d: int,
) -> list[tuple[int, set]]:
    """
    Recursive alternating-axis binary split.
    Returns list of (lot_id, cell_set) tuples.
    lot_id_counter is a mutable [int] used as a reference counter.
    """
    if not block_cells:
        return []

    rows_list = [r for r, _ in block_cells]
    cols_list = [c for _, c in block_cells]
    r_min, r_max = min(rows_list), max(rows_list)
    c_min, c_max = min(cols_list), max(cols_list)
    height = r_max - r_min + 1
    width  = c_max - c_min + 1

    can_split_h = height >= min_d * 2
    can_split_v = width  >= min_w * 2

    if not can_split_h and not can_split_v:
        lid = lot_id_counter[0]
        lot_id_counter[0] += 1
        return [(lid, block_cells)]

    split_horizontal = (height >= width) if (can_split_h and can_split_v) else can_split_h

    if split_horizontal:
        mid = (r_min + r_max) // 2
        offset = int(rng.uniform(-height * 0.2, height * 0.2))
        split_row = max(r_min + min_d, min(r_max - min_d, mid + offset))
        top    = {(r, c) for r, c in block_cells if r <= split_row}
        bottom = {(r, c) for r, c in block_cells if r > split_row}
        return (_subdivide_block(top, rng, lot_id_counter, min_w, min_d) +
                _subdivide_block(bottom, rng, lot_id_counter, min_w, min_d))
    else:
        mid = (c_min + c_max) // 2
        offset = int(rng.uniform(-width * 0.2, width * 0.2))
        split_col = max(c_min + min_w, min(c_max - min_w, mid + offset))
        left  = {(r, c) for r, c in block_cells if c <= split_col}
        right = {(r, c) for r, c in block_cells if c > split_col}
        return (_subdivide_block(left, rng, lot_id_counter, min_w, min_d) +
                _subdivide_block(right, rng, lot_id_counter, min_w, min_d))


def generate_lots(
    grid:   MapGrid,
    config: MapConfig,
    blocks: list,
    sink:   list | None = None,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 8 generator — Lot Subdivision.

    `blocks` is the list of interior block cell-sets from the blocks phase.
    Modifies grid cells in-place (sets lot_id).
    If `sink` is provided, appends each lot's cell-set to it.
    """
    yield GeneratorProgress(PHASE_LOTS, 0.0, 'Subdividing blocks into lots …')

    rng = random.Random(config.master_seed ^ SALT_LOTS)
    lot_id_counter = [0]
    all_lots: list[set] = []
    total = max(len(blocks), 1)

    for i, block in enumerate(blocks):
        if not block:
            continue
        sample_r, sample_c = next(iter(block))
        if grid[sample_r][sample_c].is_park:
            continue

        lots = _subdivide_block(block, rng, lot_id_counter, LOT_MIN_WIDTH, LOT_MIN_DEPTH)
        for lid, lot_cells in lots:
            for r, c in lot_cells:
                grid[r][c].lot_id = lid
            all_lots.append(lot_cells)

        if i % 30 == 0:
            yield GeneratorProgress(
                PHASE_LOTS,
                i / total,
                f'Lots: {lot_id_counter[0]} so far …',
            )

    if sink is not None:
        sink.extend(all_lots)

    yield GeneratorProgress(
        PHASE_LOTS, 1.0,
        f'Lot subdivision complete — {lot_id_counter[0]} lots.',
    )
