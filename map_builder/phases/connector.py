"""
map_builder/phases/connector.py
────────────────────────────────
Phase 3 — Connector Road Generation  (Harlem-Style Urban Grid)

Design rationale
────────────────
Harlem, NYC defines the archetype: long N-S avenues (Lenox Ave, Adam Clayton
Powell Blvd, Frederick Douglass Blvd) spaced ~18 cells apart, crossed by
tight E-W cross-streets roughly every 7 cells.  A single diagonal (Broadway)
slashes through the grid NW→SE.  Circle junctions (roundabouts) appear at
the busiest 3-way and 4-way intersections.

Block geometry (64×48 grid defaults):
  avenue_spacing    = 18 cells  → ~3 avenues on a 64-col map
  connector_spacing =  7 cells  → ~6 cross-streets on a 48-row map
  block ratio 2.6:1             (real Harlem ~3.6:1, compressed for small grid)
  drift_max = 1 always          → near-straight streets, authentic Harlem feel

Algorithm:
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ 1. PASS 1 — N-S avenues, spaced avenue_spacing apart.                     │
  │    drift_max = 1 — nearly straight, long north-south corridors.           │
  │                                                                            │
  │ 2. PASS 2 — E-W cross-streets, spaced connector_spacing apart.            │
  │    Same drift_max = 1.  Creates tight rectangular Harlem-style blocks.    │
  │                                                                            │
  │ 3. PASS 3 — Diagonal streets (Broadway-style, optional).                  │
  │    Noise-biased greedy spine tracer from NW to SE corner of the map.      │
  │    Uses cardinal steps only — integrates with 4-bit bitmask system.       │
  │    Count = config.diagonal_streets (default 1).                           │
  │                                                                            │
  │ 4. Bitmask pass: resolve tile IDs for all road cells.                     │
  │                                                                            │
  │ 5. Roundabout placement (after bitmask so junctions are resolved first).  │
  │    • Find connector cells with road_bitmask popcount ≥ 3 (T or X).       │
  │    • Require 3×3 area to be all-land and roundabout-free.                 │
  │    • Pick up to roundabout_count junctions, spaced avenue_spacing apart.  │
  │    • Overwrite with 3×3 roundabout tile block (roundabout_0_0 … _2_2).   │
  └───────────────────────────────────────────────────────────────────────────┘

Noise drift:
  All streets use drift_max = 1 — at most ±1 cell deviation per row/column.
  This gives the hand-drawn, slightly organic quality of a real city block
  while keeping streets clearly parallel and perpendicular.
"""
from __future__ import annotations
import math
import random
from typing import Generator

from ..constants import (
    PHASE_CONNECTOR, SALT_CONNECTOR,
    ROAD_CONNECTOR,
    LAYER_ROAD, LAYER_DECOR,
    DIRECTION_OFFSETS,
)
from ..map_state     import MapGrid, MapConfig, GeneratorProgress
from ..noise_utils   import build_perm_table, noise2d
from ..tile_registry import REGISTRY


# ── Shared land-finder ────────────────────────────────────────────────────────

def _find_land_near(
    grid:  MapGrid,
    r:     int,
    c:     int,
    max_d: int,
) -> tuple[int, int] | None:
    """
    Spiral outward from (r, c) to find the nearest land cell within max_d
    Chebyshev steps.  Returns (row, col) or None if nothing found.
    """
    for d in range(max_d + 1):
        for dr in range(-d, d + 1):
            for dc in range(-d, d + 1):
                if max(abs(dr), abs(dc)) != d:
                    continue   # only check the outer ring at distance d
                cell = grid.cell(r + dr, c + dc)
                if cell is not None and cell.is_land:
                    return (r + dr, c + dc)
    return None


# ── Street tracers ────────────────────────────────────────────────────────────

def _trace_ns_street(
    grid:      MapGrid,
    base_col:  int,
    perm:      list[int],
    drift_max: int,
) -> list[tuple[int, int]]:
    """
    Trace an N-S avenue along approximately column `base_col`.

    At each row the actual column is shifted by a smooth noise value, giving
    the subtle curvature of a real city avenue rather than a perfect line.
    drift_max = 1 → at most one cell deviation.  Water cells create gaps.
    Existing road cells create intersections without overwriting categories.
    """
    rows, cols = grid.height, grid.width
    path: list[tuple[int, int]] = []

    for r in range(rows):
        noise_val = noise2d(
            base_col / cols * 4.0,
            r        / rows * 6.0,
            perm,
        )
        c = base_col + int(round(noise_val * drift_max))
        c = max(1, min(cols - 2, c))

        cell = grid.cell(r, c)
        if cell is None or cell.is_water:
            continue
        if cell.is_road:
            continue

        cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
        path.append((r, c))

    return path


def _trace_ew_street(
    grid:      MapGrid,
    base_row:  int,
    perm:      list[int],
    drift_max: int,
) -> list[tuple[int, int]]:
    """
    Trace an E-W cross-street along approximately row `base_row`.
    Transposed mirror of _trace_ns_street.
    """
    rows, cols = grid.height, grid.width
    path: list[tuple[int, int]] = []

    for c in range(cols):
        noise_val = noise2d(
            c        / cols * 6.0,
            base_row / rows * 4.0,
            perm,
        )
        r = base_row + int(round(noise_val * drift_max))
        r = max(1, min(rows - 2, r))

        cell = grid.cell(r, c)
        if cell is None or cell.is_water:
            continue
        if cell.is_road:
            continue

        cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
        path.append((r, c))

    return path


def _trace_diagonal_street(
    grid:    MapGrid,
    perm:    list[int],
    rng:     random.Random,
    index:   int   = 0,
    organic: float = 0.25,
) -> list[tuple[int, int]]:
    """
    Trace a NW→SE diagonal street (Broadway-style) across the map.

    Uses the same noise-biased greedy spine tracer as the highway phase,
    but moves via cardinal directions only — so the result is a staircase
    diagonal that integrates correctly with the 4-bit bitmask road system.

    Multiple diagonals are offset so they don't share the same corridor:
      index=0 → starts near (row*0.08, col*0.10)
      index=1 → starts near (row*0.23, col*0.15)

    Returns the list of (row, col) cells traced.
    """
    rows, cols = grid.height, grid.width

    # Compute NW start and SE end fractions, shifted by index
    start_r = max(1, int(rows * (0.08 + index * 0.15)))
    start_c = max(1, int(cols * (0.10 + index * 0.05)))
    end_r   = min(rows - 2, int(rows * 0.92))
    end_c   = min(cols - 2, int(cols * 0.90))

    start = _find_land_near(grid, start_r, start_c, max(rows, cols) // 4)
    end   = _find_land_near(grid, end_r,   end_c,   max(rows, cols) // 4)

    if start is None or end is None:
        return []

    r, c      = start
    er, ec    = end
    path      = [(r, c)]
    visited   = {(r, c)}
    max_steps = (rows + cols) * 3

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

        nx          = (c / cols) * 2.0
        ny          = (r / rows) * 2.0
        noise_angle = noise2d(nx, ny, perm) * math.pi
        biased_dr   = dr_norm + math.sin(noise_angle) * organic
        biased_dc   = dc_norm + math.cos(noise_angle) * organic

        best_dir   = None
        best_score = -999.0

        for _d, (off_r, off_c) in DIRECTION_OFFSETS.items():
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


# ── Roundabout placer ─────────────────────────────────────────────────────────

def _place_roundabouts(
    grid:        MapGrid,
    rng:         random.Random,
    max_count:   int,
    min_spacing: int,
) -> int:
    """
    Place roundabout tiles at T-junction and 4-way connector road intersections.

    Algorithm:
      1. Scan every connector road cell; keep cells whose road_bitmask
         popcount ≥ 3 (i.e. T-junction or X-junction).
      2. For each candidate centre (r, c), verify the 3×3 neighbourhood is
         entirely in-bounds, land-or-road, and free of existing roundabout tiles.
      3. Shuffle candidates with the phase RNG for spatial variety.
      4. Greedily pick up to max_count centres spaced ≥ min_spacing apart
         (Manhattan distance).
      5. For each picked centre:
           for dr in {-1, 0, +1}, dc in {-1, 0, +1}:
               tile = roundabout_{dr+1}_{dc+1}
               cell.set_road(tile, ROAD_CONNECTOR)
         This overwrites the bitmask-resolved tile ID but keeps road_category.

    Returns the number of roundabouts actually placed.
    """
    # ── Phase 1: collect candidates ───────────────────────────────────────────
    candidates: list[tuple[int, int]] = []

    for r, c, cell in grid.all_cells():
        if not cell.is_road or cell.road_category != ROAD_CONNECTOR:
            continue
        tile_id = cell.layers[LAYER_ROAD] or ''
        if tile_id.startswith('roundabout_'):
            continue                           # skip already-placed roundabouts

        if bin(grid.road_bitmask(r, c, ROAD_CONNECTOR)).count('1') < 3:
            continue                           # must be T or X junction

        # 3×3 neighbourhood: all cells must be in-bounds and not water,
        # and none can already be a roundabout tile.
        ok = True
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nbr = grid.cell(r + dr, c + dc)
                if nbr is None or nbr.is_water:
                    ok = False
                    break
                if (nbr.layers[LAYER_ROAD] or '').startswith('roundabout_'):
                    ok = False
                    break
            if not ok:
                break

        if ok:
            candidates.append((r, c))

    # ── Phase 2: select with spacing constraint ───────────────────────────────
    rng.shuffle(candidates)

    placed_centres: list[tuple[int, int]] = []
    placed_count = 0

    for cr, cc in candidates:
        if placed_count >= max_count:
            break

        # Manhattan spacing check against all previously placed roundabouts
        if any(
            abs(cr - pr) + abs(cc - pc) < min_spacing
            for pr, pc in placed_centres
        ):
            continue

        # ── Phase 3: stamp 3×3 roundabout tiles ──────────────────────────────
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cell = grid.cell(cr + dr, cc + dc)
                if cell is None:
                    continue
                tile_id = f'roundabout_{dr + 1}_{dc + 1}'
                cell.set_road(tile_id, ROAD_CONNECTOR, variation=0)

        placed_centres.append((cr, cc))
        placed_count += 1

    return placed_count


# ── Gap-fill helper ───────────────────────────────────────────────────────────

def _gap_fill_positions(
    placed:      list[int],
    boundary_lo: int,
    boundary_hi: int,
    block_size:  int,
    rng:         random.Random,
    probability: float = 0.65,
) -> list[int]:
    """
    Return secondary street positions that subdivide gaps larger than block_size.

    Scans all gaps between placed streets (and both map edges). Wherever a gap
    exceeds block_size, the midpoint is added with `probability` chance. This
    fills in blocks made oversized by the density filter without forcing a
    perfectly uniform grid.
    """
    boundaries = sorted({boundary_lo, boundary_hi} | set(placed))
    secondary: list[int] = []
    for i in range(len(boundaries) - 1):
        gap = boundaries[i + 1] - boundaries[i]
        if gap > block_size and rng.random() < probability:
            secondary.append((boundaries[i] + boundaries[i + 1]) // 2)
    return secondary


# ── Public phase generator ────────────────────────────────────────────────────

def generate_connectors(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 3 generator — Harlem-Style Urban Street Grid.
    Modifies `grid` in-place; yields GeneratorProgress throughout.

    Five-pass structure:
      Pass 1: N-S avenues (config.avenue_spacing cells apart)
      Pass 2: E-W cross-streets (config.connector_spacing cells apart)
      Pass 3: Diagonal Broadway-style streets (config.diagonal_streets count)
      Pass 4: Bitmask tile-ID resolution for all road cells
      Pass 5: Roundabout placement at high-connectivity junctions
    """
    rng  = random.Random(config.master_seed ^ SALT_CONNECTOR)
    perm = build_perm_table(config.master_seed ^ SALT_CONNECTOR)

    yield GeneratorProgress(PHASE_CONNECTOR, 0.0, 'Planning Harlem-style street grid …')

    rows, cols = grid.height, grid.width

    # ── Block dimensions ──────────────────────────────────────────────────────
    # Avenues: wide N-S spacing (Harlem's long corridors like Lenox, ACP Blvd)
    av_block = max(
        config.avenue_spacing,
        config.min_block_depth * 2 + 2,
    )
    # Cross-streets: tight E-W spacing (Harlem's short blocks ~1 avenue block)
    cs_block = max(
        config.connector_spacing,
        config.min_block_depth * 2 + 2,
    )

    # Harlem streets are almost perfectly straight — fix drift at 1 cell max.
    # connector_turn_bias still tunes the noise amplitude but caps at 1.
    drift_max = min(1, max(1, round(config.connector_turn_bias * 10)))

    # ── Grid line positions ───────────────────────────────────────────────────
    ns_bases = list(range(av_block, cols - av_block // 2, av_block))
    ew_bases = list(range(cs_block, rows - cs_block // 2, cs_block))

    if not ns_bases and not ew_bases:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 1.0,
            'Grid too small for street layout at current block sizes.'
        )
        return

    # Apply density: randomly drop (1 - connector_density) fraction of lines.
    rng.shuffle(ns_bases)
    rng.shuffle(ew_bases)
    keep_ns  = max(1, round(len(ns_bases) * config.connector_density))
    keep_ew  = max(1, round(len(ew_bases) * config.connector_density))
    ns_bases = sorted(ns_bases[:keep_ns])
    ew_bases = sorted(ew_bases[:keep_ew])

    total_streets = len(ns_bases) + len(ew_bases)
    total_cells   = 0
    streets_done  = 0

    yield GeneratorProgress(
        PHASE_CONNECTOR, 0.02,
        f'Harlem grid: {len(ns_bases)} avenues (±{av_block}px) '
        f'+ {len(ew_bases)} cross-streets (±{cs_block}px), drift=±{drift_max}'
    )

    # ── Pass 1: N-S avenues ───────────────────────────────────────────────────
    for base_col in ns_bases:
        path          = _trace_ns_street(grid, base_col, perm, drift_max)
        total_cells  += len(path)
        streets_done += 1

        if streets_done % 3 == 0 or streets_done == len(ns_bases):
            yield GeneratorProgress(
                PHASE_CONNECTOR,
                0.02 + 0.35 * streets_done / max(total_streets, 1),
                f'Avenues: {streets_done}/{len(ns_bases)} '
                f'({total_cells} cells placed) …'
            )

    # ── Pass 2: E-W cross-streets ─────────────────────────────────────────────
    for i, base_row in enumerate(ew_bases):
        path          = _trace_ew_street(grid, base_row, perm, drift_max)
        total_cells  += len(path)
        streets_done += 1

        if i % 3 == 0 or i == len(ew_bases) - 1:
            yield GeneratorProgress(
                PHASE_CONNECTOR,
                0.37 + 0.28 * (i + 1) / max(len(ew_bases), 1),
                f'Cross-streets: {i + 1}/{len(ew_bases)} '
                f'({total_cells} cells placed) …'
            )

    # ── Pass 2.5: Gap-fill secondary streets ─────────────────────────────────
    # After the density filter drops some streets, fill any oversized gaps so no
    # block is more than ~1.5× the intended spacing.
    sec_ns = _gap_fill_positions(ns_bases, 0, cols - 1, av_block, rng)
    sec_ew = _gap_fill_positions(ew_bases, 0, rows - 1, cs_block, rng)

    sec_cells = 0
    for base_col in sec_ns:
        path       = _trace_ns_street(grid, base_col, perm, drift_max)
        sec_cells += len(path)
        total_cells += len(path)
    for base_row in sec_ew:
        path       = _trace_ew_street(grid, base_row, perm, drift_max)
        sec_cells += len(path)
        total_cells += len(path)

    if sec_cells > 0:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 0.66,
            f'Gap fill: +{len(sec_ns)} avenues, +{len(sec_ew)} cross-streets '
            f'({sec_cells} cells)'
        )

    # ── Pass 3: Diagonal streets (Broadway-style) ─────────────────────────────
    diag_count = config.diagonal_streets
    diag_cells = 0

    for i in range(diag_count):
        diag_path = _trace_diagonal_street(grid, perm, rng, index=i)
        for dr, dc in diag_path:
            cell = grid.cell(dr, dc)
            if cell is not None and cell.is_land and not cell.is_road:
                cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
        diag_cells  += len(diag_path)
        total_cells += len(diag_path)

    if diag_count > 0:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 0.67,
            f'{diag_count} diagonal street(s) — {diag_cells} cells …'
        )

    # ── Pass 4: Bitmask tile-ID resolution ────────────────────────────────────
    yield GeneratorProgress(PHASE_CONNECTOR, 0.72, 'Resolving road tile variants …')

    for r, c, cell in grid.all_cells():
        if not cell.is_road:
            continue
        # Preserve any roundabout tiles that might have been pre-placed
        tile_id = cell.layers[LAYER_ROAD] or ''
        if tile_id.startswith('roundabout_'):
            continue
        mask    = grid.road_bitmask(r, c, ROAD_CONNECTOR)
        tile_id = REGISTRY.resolve_road_tile_id(mask, cell.road_category)
        cell.layers[LAYER_ROAD] = tile_id

    # ── Pass 4b: Road surface variation ──────────────────────────────────────
    # Tiles like TILE_ROAD_STRAIGHT_NS register multiple sprite variants
    # (plain asphalt, dashed centre line, yellow centre line, etc.) from
    # roads.png bands 0-3.  Randomly assign a variant index per cell so the
    # street grid looks hand-drawn rather than copy-pasted.
    # Does not touch roundabout tiles, T/X structural tiles, or highways.
    for r, c, cell in grid.all_cells():
        if not cell.is_road or cell.road_category != ROAD_CONNECTOR:
            continue
        tile_id = cell.layers[LAYER_ROAD] or ''
        if tile_id.startswith('roundabout_'):
            continue
        variants = REGISTRY.get_variants(tile_id)
        if len(variants) > 1:
            cell.variation[LAYER_ROAD] = rng.randrange(len(variants))

    # ── Pass 5: Roundabout placement ──────────────────────────────────────────
    rb_count = config.roundabout_count
    placed   = 0

    if rb_count > 0:
        yield GeneratorProgress(PHASE_CONNECTOR, 0.88, 'Placing roundabouts at junctions …')
        # Allow roundabouts every 2× cross-street spacings so they appear
        # denser and more naturally distributed across the city.
        min_spacing = max(config.connector_spacing * 2, config.avenue_spacing // 2)
        placed = _place_roundabouts(grid, rng, rb_count, min_spacing)

    # ── Pass 6: Junction markings ─────────────────────────────────────────────
    # Place road-marking tiles (crosswalks, yield lines, turn arrows) onto
    # LAYER_DECOR at every T and X connector intersection that was NOT
    # converted to a roundabout.  The game renderer draws these on top of
    # the structural road tile, giving each junction a distinct visual identity.
    _X_MARKINGS = ['road_marking_crosswalk', 'road_marking_crosswalk_b']
    _T_MARKINGS = [
        'road_marking_yield',       'road_marking_yield_dots',
        'road_marking_arrow_l',     'road_marking_arrow_r',
        'road_marking_arrow_s',     'road_marking_fork',
        'road_marking_merge',
    ]

    junctions_marked = 0
    for r, c, cell in grid.all_cells():
        if not cell.is_road or cell.road_category != ROAD_CONNECTOR:
            continue
        tile_id = cell.layers[LAYER_ROAD] or ''
        if tile_id.startswith('roundabout_'):
            continue
        popcount = bin(grid.road_bitmask(r, c, ROAD_CONNECTOR)).count('1')
        if popcount == 4:                          # X-junction — always mark
            cell.set_decor(rng.choice(_X_MARKINGS))
            junctions_marked += 1
        elif popcount == 3 and rng.random() < 0.6:  # T-junction — 60% marked
            cell.set_decor(rng.choice(_T_MARKINGS))
            junctions_marked += 1

    yield GeneratorProgress(
        PHASE_CONNECTOR, 1.0,
        f'Street grid complete — {total_cells} cells, '
        f'{len(ns_bases)} avenues + {len(ew_bases)} cross-streets + '
        f'{diag_count} diagonal(s) + {placed} roundabout(s), '
        f'{junctions_marked} junction markings.'
    )
