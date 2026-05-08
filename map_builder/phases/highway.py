"""
map_builder/phases/highway.py
──────────────────────────────
Phase 2 — Highway Generation

Algorithm  (noise-biased spine tracer with separate N-S / E-W axis control):

  Highway axes are controlled independently to reflect real coastal city structure:

    N-S (Y-axis) highways — run north-to-south, parallel to the coastline.
      These are the dominant arterials of a coastal city (PCH on the US Pacific
      Coast, the seafront boulevards of Barcelona and Harlem's riverside drives).
      Count is sampled each map from triangular(ns_min, ns_max, mode=ns_min),
      so most seeds produce ns_min highways while rare seeds approach ns_max.
      Default: ns_min=2, ns_max=5  → usually 2, occasionally 3–5.

    E-W (X-axis) highways — run east-to-west, perpendicular to the coastline.
      Cross-routes heading inland from the coast.  Often absent (replaced by
      connector cross-streets at the local grid scale).
      Default: ew_min=0, ew_max=3  → usually 0–1, rarely 2–3.

  Real-world reference (10m/cell):
    Harlem/Manhattan : 2 N-S highways (East/West Side Drive), 1-2 E-W.
    Barcelona        : 2-3 N-S coastal roads, 0-1 E-W at highway scale.
    Paris            : radial pattern — 2-3 N-S, 1-2 E-W grands boulevards.
    London           : radial ring roads — 2-3 N-S, 1 E-W (North/South Circ.).

  Spine algorithm:
    At each step score 4 cardinal directions against goal_dir + noise_perturbation.
    Pick highest-scoring direction toward unvisited land.  Back-track one cell
    when stuck; abort if still stuck after backtrack.

  Tile resolution:
    After all spines: bitmask pass → REGISTRY.resolve_road_tile_id().
    Highway tiles get a '_hw' suffix selecting the elevated-deck sprite row.

Yields GeneratorProgress after each highway spine.
"""
from __future__ import annotations
import math
import random
from typing import Generator

from ..constants import (
    PHASE_HIGHWAY, SALT_HIGHWAY,
    ROAD_HIGHWAY,
    N, E, S, W, DIRECTION_OFFSETS,
    ROAD_BITMASK_TO_TILE,
    LAYER_ROAD,
)
from ..map_state     import MapGrid, MapConfig, GeneratorProgress
from ..noise_utils   import build_perm_table, noise2d
from ..tile_registry import REGISTRY


# ── Edge-boundary scanner ─────────────────────────────────────────────────────

def _land_edge_points(
    grid:  MapGrid,
    side:  str,          # 'north' | 'south' | 'east' | 'west'
    rng:   random.Random,
    count: int,
) -> list[tuple[int, int]]:
    """
    Return `count` land cells on (or just inside) the requested map edge.

    For each row/column along the edge, scans inward until the first land cell
    is found — so coastal maps (where the outer border is water) still produce
    valid highway entry points at the actual shoreline.

    Candidates are evenly spaced along the edge with a small RNG jitter, so
    multiple highways on the same axis start at well-separated positions.
    """
    rows, cols = grid.height, grid.width
    candidates: list[tuple[int, int]] = []

    if side == 'north':
        for c in range(cols):
            for r in range(rows):
                if grid[r][c].is_land:
                    candidates.append((r, c))
                    break
    elif side == 'south':
        for c in range(cols):
            for r in range(rows - 1, -1, -1):
                if grid[r][c].is_land:
                    candidates.append((r, c))
                    break
    elif side == 'west':
        for r in range(rows):
            for c in range(cols):
                if grid[r][c].is_land:
                    candidates.append((r, c))
                    break
    else:  # 'east'
        for r in range(rows):
            for c in range(cols - 1, -1, -1):
                if grid[r][c].is_land:
                    candidates.append((r, c))
                    break

    if not candidates:
        return []

    n    = min(count, len(candidates))
    step = max(1, len(candidates) // (n + 1))
    result: list[tuple[int, int]] = []
    for i in range(1, n + 1):
        jitter = rng.randint(-max(1, step // 3), max(1, step // 3))
        idx    = max(0, min(len(candidates) - 1, i * step + jitter))
        result.append(candidates[idx])
    return result


# ── Spine tracer ──────────────────────────────────────────────────────────────

def _trace_highway_spine(
    grid:    MapGrid,
    start:   tuple[int, int],
    end:     tuple[int, int],
    perm:    list[int],
    rng:     random.Random,
    organic: float,
) -> list[tuple[int, int]]:
    """
    Walk from `start` to `end` staying on land.

    At each step the best cardinal direction is chosen by dot-scoring against a
    goal vector slightly bent by low-frequency noise (organic feel).
    Back-tracks one cell when fully stuck; breaks if still stuck.
    """
    r, c      = start
    er, ec    = end
    path      = [(r, c)]
    visited   = {(r, c)}
    max_steps = (grid.height + grid.width) * 3

    for _ in range(max_steps):
        if (r, c) == (er, ec):
            break

        dr_goal = er - r
        dc_goal = ec - c
        dist    = math.hypot(dr_goal, dc_goal)
        if dist == 0:
            break

        dr_norm = dr_goal / dist
        dc_norm = dc_goal / dist

        nx          = (c / grid.width)  * 2.0
        ny          = (r / grid.height) * 2.0
        noise_angle = noise2d(nx, ny, perm) * math.pi
        biased_dr   = dr_norm + math.sin(noise_angle) * organic
        biased_dc   = dc_norm + math.cos(noise_angle) * organic

        best_dir   = None
        best_score = -999.0
        for d, (off_r, off_c) in DIRECTION_OFFSETS.items():
            nr, nc = r + off_r, c + off_c
            if (
                grid.in_bounds(nr, nc)
                and grid[nr][nc].is_land
                and (nr, nc) not in visited
            ):
                score = off_r * biased_dr + off_c * biased_dc
                if score > best_score:
                    best_score = score
                    best_dir   = (off_r, off_c)

        if best_dir is None:
            if len(path) > 1:
                path.pop()
                r, c = path[-1]
                visited.discard((r, c))
            else:
                break
            continue

        r += best_dir[0]
        c += best_dir[1]
        visited.add((r, c))
        path.append((r, c))

    return path


# ── Tile resolver ─────────────────────────────────────────────────────────────

def _resolve_road_tiles(grid: MapGrid) -> None:
    """Bitmask pass: assign the correct tile_id to every highway road cell."""
    for r, c, cell in grid.all_cells():
        if not cell.is_road or cell.road_category != ROAD_HIGHWAY:
            continue
        mask    = grid.road_bitmask(r, c, ROAD_HIGHWAY)
        tile_id = REGISTRY.resolve_road_tile_id(mask, cell.road_category)
        cell.layers[LAYER_ROAD] = tile_id


# ── Public phase generator ────────────────────────────────────────────────────

def generate_highways(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 2 generator.  Modifies `grid` in-place.

    Samples N-S and E-W highway counts independently from triangular
    distributions biased toward the configured minimums, then traces each
    spine and runs the bitmask tile-ID pass on completion.
    """
    rng  = random.Random(config.master_seed ^ SALT_HIGHWAY)
    perm = build_perm_table(config.master_seed ^ SALT_HIGHWAY)

    yield GeneratorProgress(PHASE_HIGHWAY, 0.0, 'Sampling highway layout …')

    # ── Sample counts — triangular(low, high, mode=low) ──────────────────────
    # Right-skewed: most seeds cluster near the minimum, rare seeds reach max.
    ns_count = max(
        config.highway_ns_min,
        min(config.highway_ns_max,
            int(rng.triangular(config.highway_ns_min,
                               config.highway_ns_max + 1,
                               config.highway_ns_min))),
    )
    ew_count = max(
        config.highway_ew_min,
        min(config.highway_ew_max,
            int(rng.triangular(config.highway_ew_min,
                               config.highway_ew_max + 1,
                               config.highway_ew_min))),
    )

    total           = ns_count + ew_count
    highways_placed = 0

    yield GeneratorProgress(
        PHASE_HIGHWAY, 0.02,
        f'Highway layout: {ns_count} N-S (Y-axis) + {ew_count} E-W (X-axis) = {total} total'
    )

    if total == 0:
        yield GeneratorProgress(PHASE_HIGHWAY, 1.0, 'No highways configured — skipping.')
        return

    # ── Batch-request edge points for each axis ───────────────────────────────
    # Requesting all ns_count starts at once guarantees they are evenly spread
    # along the north edge (different columns → different latitudes).
    ns_starts = _land_edge_points(grid, 'north', rng, ns_count) if ns_count > 0 else []
    ns_ends   = _land_edge_points(grid, 'south', rng, ns_count) if ns_count > 0 else []
    ew_starts = _land_edge_points(grid, 'west',  rng, ew_count) if ew_count > 0 else []
    ew_ends   = _land_edge_points(grid, 'east',  rng, ew_count) if ew_count > 0 else []

    # ── N-S highways (north → south) ─────────────────────────────────────────
    for i in range(min(len(ns_starts), len(ns_ends))):
        start, end = ns_starts[i], ns_ends[i]
        spine = _trace_highway_spine(grid, start, end, perm, rng, config.highway_organic)

        for sr, sc in spine:
            if not grid[sr][sc].is_water:
                grid[sr][sc].set_road('road_1010', ROAD_HIGHWAY, variation=0)

        highways_placed += 1
        yield GeneratorProgress(
            PHASE_HIGHWAY,
            0.04 + 0.44 * highways_placed / total,
            f'N-S highway {i + 1}/{ns_count} — {len(spine)} cells.'
        )

    # ── E-W highways (west → east) ────────────────────────────────────────────
    for i in range(min(len(ew_starts), len(ew_ends))):
        start, end = ew_starts[i], ew_ends[i]
        spine = _trace_highway_spine(grid, start, end, perm, rng, config.highway_organic)

        for sr, sc in spine:
            if not grid[sr][sc].is_water:
                grid[sr][sc].set_road('road_1010', ROAD_HIGHWAY, variation=0)

        highways_placed += 1
        yield GeneratorProgress(
            PHASE_HIGHWAY,
            0.04 + 0.44 * highways_placed / total,
            f'E-W highway {i + 1}/{ew_count} — {len(spine)} cells.'
        )

    yield GeneratorProgress(PHASE_HIGHWAY, 0.50, 'Resolving highway tile variants …')
    _resolve_road_tiles(grid)

    yield GeneratorProgress(
        PHASE_HIGHWAY, 1.0,
        f'Highways complete — {highways_placed} spines '
        f'({ns_count} N-S + {ew_count} E-W).'
    )
