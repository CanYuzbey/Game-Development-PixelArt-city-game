"""
map_builder/phases/parks.py
────────────────────────────
Phase 7 — Park Placement  (Sprint 3 rewrite)

Design goals:
  • Parks should be LARGE ENOUGH to read visually — min 20 cells (200m²)
  • At most PARK_MAX_PER_ZONE parks per zone to avoid city feeling like a forest
  • Prefer mid-size blocks (25-120 cells) — big enough to look like a real park,
    small enough not to dominate the zone
  • Use a priority score: blocks closest to ideal size win; blocks too close to an
    existing park are penalised (minimum separation = 8 cells Chebyshev)
  • Mark every cell in selected blocks with is_park = True

Sprint 2 bug fixed: the old algorithm chose tiny blocks (1-9 cells) as parks
because connector_spacing=6 created many small blocks.  Those appeared as green
specks invisible at normal zoom.  This version requires PARK_MIN_AREA cells.
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_PARKS, SALT_PARKS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    PARK_MIN_AREA, PARK_IDEAL_MIN, PARK_IDEAL_MAX,
    PARK_CBD_PROBABILITY, PARK_MIDTOWN_PROBABILITY, PARK_RESIDENTIAL_PROBABILITY,
    ROLE_WALKABLE_PARK,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress


# Minimum Chebyshev distance between any two park block centres.
_PARK_MIN_SEPARATION: int = 10


def _block_centroid(block: set) -> tuple[float, float]:
    rs = [r for r, _ in block]
    cs = [c for _, c in block]
    return sum(rs) / len(rs), sum(cs) / len(cs)


def _block_compactness(block: set) -> float:
    """
    Return fill ratio of block cells vs bounding box area (0..1).
    1.0 = perfectly rectangular; lower = L-shaped / irregular.
    Blocks below 0.55 are too irregular to be parks.
    """
    if not block:
        return 0.0
    rs = [r for r, _ in block]
    cs = [c for _, c in block]
    bbox = (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1)
    return len(block) / bbox if bbox > 0 else 0.0


def _chebyshev(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _park_score(area: int) -> float:
    """
    Score ∈ [0, 1]: peaks at PARK_IDEAL_MIN–PARK_IDEAL_MAX cells.
    Blocks outside [PARK_MIN_AREA, PARK_IDEAL_MAX] score 0.
    """
    if area < PARK_MIN_AREA or area > PARK_IDEAL_MAX:
        return 0.0
    ideal_mid = (PARK_IDEAL_MIN + PARK_IDEAL_MAX) / 2
    # triangle score: 1.0 at ideal_mid, 0 at the edges
    dist = abs(area - ideal_mid) / (ideal_mid - PARK_MIN_AREA + 1)
    return max(0.0, 1.0 - dist)


def generate_parks(
    grid:   MapGrid,
    config: MapConfig,
    blocks: list,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 7 generator — Park Placement.

    `blocks` is the list of interior block cell-sets produced by the blocks phase.
    Modifies grid cells in-place (sets is_park = True).
    """
    yield GeneratorProgress(PHASE_PARKS, 0.0, 'Placing parks (priority scoring) …')

    rng = random.Random(config.master_seed ^ SALT_PARKS)

    # Dynamic park quota: ~1 park per 500 land cells per zone, min 1, max 4
    land_count = sum(1 for _, _, c in grid.all_cells() if c.is_land)
    dynamic_max = max(1, min(4, land_count // 500))

    # ── Build candidate list per zone ─────────────────────────────────────────
    candidates: dict[int, list] = {
        ZONE_CBD: [], ZONE_MIDTOWN: [], ZONE_RESIDENTIAL: [],
    }
    zone_prob: dict[int, float] = {
        ZONE_CBD:          PARK_CBD_PROBABILITY,
        ZONE_MIDTOWN:      PARK_MIDTOWN_PROBABILITY,
        ZONE_RESIDENTIAL:  PARK_RESIDENTIAL_PROBABILITY,
    }

    for block in blocks:
        if not block:
            continue
        area = len(block)
        score = _park_score(area)
        if score <= 0.0:
            continue
        # Reject highly irregular (L-shaped) blocks as parks
        if _block_compactness(block) < 0.55:
            continue
        sample_r, sample_c = next(iter(block))
        zone = grid[sample_r][sample_c].zone_id
        if zone in candidates:
            centroid = _block_centroid(block)
            candidates[zone].append((score, rng.random(), centroid, block))

    # ── Per-zone greedy selection ──────────────────────────────────────────────
    park_count = 0
    placed_centroids: list[tuple[float, float]] = []

    for zone in (ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL):
        zone_list = candidates[zone]
        if not zone_list:
            continue

        # Sort: highest score first; random second-key for tie-breaking
        zone_list.sort(key=lambda x: (-x[0], x[1]))

        zone_parks = 0
        prob = zone_prob[zone]

        for score, _, centroid, block in zone_list:
            if zone_parks >= dynamic_max:
                break

            # Probability gate (gives stochastic variety across seeds)
            if rng.random() > prob:
                continue

            # Separation check — don't cluster parks
            too_close = any(
                _chebyshev(centroid, pc) < _PARK_MIN_SEPARATION
                for pc in placed_centroids
            )
            if too_close:
                continue

            # ── Select this block as a park ──────────────────────────────────
            for r, c in block:
                grid[r][c].is_park = True
                grid[r][c].tile_role = ROLE_WALKABLE_PARK
            placed_centroids.append(centroid)
            zone_parks += 1
            park_count += 1

    yield GeneratorProgress(
        PHASE_PARKS, 1.0,
        f'Park placement complete — {park_count} parks placed '
        f'(min area: {PARK_MIN_AREA}, ideal: {PARK_IDEAL_MIN}–{PARK_IDEAL_MAX} cells).',
    )
