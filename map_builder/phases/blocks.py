"""
map_builder/phases/blocks.py
─────────────────────────────
Phase 6 — City Block Detection

BFS flood-fill over non-road cells to identify enclosed city blocks.
Cells that touch the map edge belong to the 'exterior' region and receive
BLOCK_EXTERIOR_ID (-1).  Interior enclosed regions are numbered 0, 1, 2, …
and stored in the generator's `blocks` list for downstream phases (parks, lots).
"""
from __future__ import annotations
from collections import deque
from typing import Generator

from ..constants import PHASE_BLOCKS, BLOCK_EXTERIOR_ID
from ..map_state import MapGrid, MapConfig, GeneratorProgress


def generate_blocks(
    grid: MapGrid,
    config: MapConfig,
    sink: list | None = None,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 6 generator — Block Detection.

    Modifies grid cells in-place (sets block_id).
    If `sink` is provided, appends each interior block's cell-set to it.
    """
    yield GeneratorProgress(PHASE_BLOCKS, 0.0, 'Detecting city blocks via BFS …')

    rows, cols = grid.height, grid.width
    visited = [[False] * cols for _ in range(rows)]
    block_counter = 0
    found_blocks: list[set] = []

    for start_r in range(rows):
        for start_c in range(cols):
            cell = grid[start_r][start_c]
            if visited[start_r][start_c] or cell.is_road or cell.is_water:
                visited[start_r][start_c] = True
                continue

            region: list[tuple[int, int]] = []
            queue: deque = deque([(start_r, start_c)])
            visited[start_r][start_c] = True
            touches_edge = False

            while queue:
                r, c = queue.popleft()
                region.append((r, c))
                if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                    touches_edge = True
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if not visited[nr][nc] and not grid[nr][nc].is_road and not grid[nr][nc].is_water:
                            visited[nr][nc] = True
                            queue.append((nr, nc))

            if touches_edge:
                for r, c in region:
                    grid[r][c].block_id = BLOCK_EXTERIOR_ID
            else:
                bid = block_counter
                block_counter += 1
                block_set: set[tuple[int, int]] = set(region)
                for r, c in region:
                    grid[r][c].block_id = bid
                found_blocks.append(block_set)

    if sink is not None:
        sink.extend(found_blocks)

    yield GeneratorProgress(
        PHASE_BLOCKS, 1.0,
        f'Block detection complete — {block_counter} interior blocks found.',
    )
