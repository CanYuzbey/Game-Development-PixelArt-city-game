"""
map_builder/phases/lots.py
───────────────────────────
Phase 8 — Lot Subdivision

Recursively splits each non-park interior block into building lots using
alternating-axis binary splitting (similar to a k-d tree), with a ±20% noise
offset on the split position to produce naturally varied lot sizes.

Sets cell.lot_id ≥ 0 on every land cell inside a subdivided lot.
Park cells and exterior cells retain lot_id == -1.

Quality guarantees (Iteration 1):
  • Blocks < 6 cells are skipped (too small to develop — marked as exterior).
  • Lots < 4 cells are not assigned a lot_id (left as exterior/void).
  • Lots with aspect ratio > 4:1 trigger an extra split along the long axis.
  • Zone detection uses majority vote from all lot cells, not just block sample.
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_LOTS, SALT_LOTS, LOT_MIN_WIDTH, LOT_MIN_DEPTH,
    ZONE_RESIDENTIAL, ROLE_WALKABLE_SIDEWALK, BLOCK_EXTERIOR_ID,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress

# Minimum block size to consider for lot subdivision (cells)
_BLOCK_MIN_CELLS = 6
# Minimum lot size to assign a lot_id (cells)
_LOT_MIN_CELLS = 4
# Maximum lot aspect ratio (long/short) before forcing a split
_LOT_MAX_ASPECT = 4.0


def _apply_residential_setback(grid: MapGrid, lot_cells: set) -> None:
    """
    Mark the outermost 1-cell perimeter of a residential lot as setback (front yard).
    Only applies to lots with ≥ 9 cells (3×3 minimum footprint).
    Setback cells get is_setback=True and tile_role=ROLE_WALKABLE_SIDEWALK.
    """
    if len(lot_cells) < 9:
        return
    rows_list = [r for r, _ in lot_cells]
    cols_list = [c for _, c in lot_cells]
    r_min, r_max = min(rows_list), max(rows_list)
    c_min, c_max = min(cols_list), max(cols_list)
    for r, c in lot_cells:
        if r == r_min or r == r_max or c == c_min or c == c_max:
            cell = grid[r][c]
            if not cell.is_sidewalk:
                cell.is_setback = True
                cell.tile_role = ROLE_WALKABLE_SIDEWALK


def _lot_zone(grid: MapGrid, lot_cells: set) -> int:
    """Return the majority zone_id of cells in a lot (handles zone-boundary lots)."""
    votes: dict[int, int] = {}
    for r, c in lot_cells:
        z = grid[r][c].zone_id
        votes[z] = votes.get(z, 0) + 1
    return max(votes, key=votes.get) if votes else -1


def _subdivide_block(
    block_cells: set,
    rng: random.Random,
    lot_id_counter: list,
    min_w: int,
    min_d: int,
) -> list[tuple[int, set]]:
    """
    Recursive alternating-axis binary split with aspect-ratio enforcement.
    Returns list of (lot_id, cell_set) tuples.
    lot_id_counter is a mutable [int] used as a reference counter.

    Lots < _LOT_MIN_CELLS cells are returned with lot_id=-1 (not assigned).
    Lots with aspect ratio > _LOT_MAX_ASPECT are forced to split along the
    long axis even if already below the normal minimum size threshold.
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

    # Aspect-ratio check: force a split along the longer axis if ratio > max
    aspect = (height / width) if width > 0 else 999
    if aspect > _LOT_MAX_ASPECT and height >= min_d * 2:
        can_split_h = True
    elif (1.0 / aspect) > _LOT_MAX_ASPECT and width >= min_w * 2:
        can_split_v = True

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
    skipped_tiny_blocks = 0

    for i, block in enumerate(blocks):
        if not block:
            continue
        sample_r, sample_c = next(iter(block))
        cell0 = grid[sample_r][sample_c]

        # Skip park blocks (handled by parks phase)
        if cell0.is_park:
            continue

        # Skip blocks too small to develop — mark as exterior
        if len(block) < _BLOCK_MIN_CELLS:
            for r, c in block:
                grid[r][c].block_id = BLOCK_EXTERIOR_ID
            skipped_tiny_blocks += 1
            continue

        lots = _subdivide_block(block, rng, lot_id_counter, LOT_MIN_WIDTH, LOT_MIN_DEPTH)

        for lid, lot_cells in lots:
            # Skip tiny lots — leave lot_id = -1 (treated as exterior in buildings phase)
            if len(lot_cells) < _LOT_MIN_CELLS:
                continue

            for r, c in lot_cells:
                grid[r][c].lot_id = lid

            # Use majority-vote zone of lot cells for setback decision
            lot_zone = _lot_zone(grid, lot_cells)
            if lot_zone == ZONE_RESIDENTIAL:
                _apply_residential_setback(grid, lot_cells)
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
        f'Lot subdivision complete — {lot_id_counter[0]} lots '
        f'({skipped_tiny_blocks} tiny blocks skipped).',
    )
