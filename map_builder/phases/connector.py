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
  drift_max = 1..3              → center streets nearly straight; outer streets curve more

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
  Center streets use drift_max = 1 (CBD grid feel); outer streets scale up to
  drift_max + 2 for organic curvature in residential zones.  All streets stay
  clearly parallel/perpendicular — at most a few cells of smooth deviation.
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
    ZONE_RESIDENTIAL,
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
    drift_max = 1 → at most one cell deviation per step.  Water cells create
    gaps.  Existing road cells create intersections without overwriting.

    Connectivity guarantee: when the column shifts by 1 between consecutive
    rows, a bridge cell is inserted so no two consecutive placed cells are
    only diagonally adjacent (which the 4-bit bitmask system doesn't connect).
    """
    rows, cols = grid.height, grid.width
    path: list[tuple[int, int]] = []
    prev_c = base_col
    prev_r_placed: int | None = None
    prev_c_placed: int | None = None

    for r in range(rows):
        noise_val = noise2d(
            base_col / cols * 4.0,
            r        / rows * 6.0,
            perm,
        )
        c = base_col + int(round(noise_val * drift_max))
        c = max(1, min(cols - 2, c))
        c = max(prev_c - 1, min(prev_c + 1, c))
        prev_c = c

        # Bridge cell: if previous placed cell at (prev_r, prev_c_placed) and
        # current at (r, c) are only diagonally adjacent, add (r, prev_c_placed).
        if prev_c_placed is not None and prev_r_placed is not None:
            if abs(r - prev_r_placed) == 1 and abs(c - prev_c_placed) == 1:
                bridge_c = prev_c_placed
                bridge_r = r
                bridge_cell = grid.cell(bridge_r, bridge_c)
                if bridge_cell is not None and bridge_cell.is_land and not bridge_cell.is_road and not bridge_cell.is_water:
                    bridge_cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
                    path.append((bridge_r, bridge_c))

        cell = grid.cell(r, c)
        if cell is not None and cell.is_land and not cell.is_water:
            if not cell.is_road:
                cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
                path.append((r, c))
            prev_r_placed = r
            prev_c_placed = c

    return path


def _trace_ew_street(
    grid:      MapGrid,
    base_row:  int,
    perm:      list[int],
    drift_max: int,
) -> list[tuple[int, int]]:
    """
    Trace an E-W cross-street along approximately row `base_row`.
    Transposed mirror of _trace_ns_street with the same connectivity guarantee.
    """
    rows, cols = grid.height, grid.width
    path: list[tuple[int, int]] = []
    prev_r = base_row
    prev_r_placed: int | None = None
    prev_c_placed: int | None = None

    for c in range(cols):
        noise_val = noise2d(
            c        / cols * 6.0,
            base_row / rows * 4.0,
            perm,
        )
        r = base_row + int(round(noise_val * drift_max))
        r = max(1, min(rows - 2, r))
        r = max(prev_r - 1, min(prev_r + 1, r))
        prev_r = r

        # Bridge cell: fill diagonal gap between consecutive placed cells
        if prev_r_placed is not None and prev_c_placed is not None:
            if abs(r - prev_r_placed) == 1 and abs(c - prev_c_placed) == 1:
                bridge_r = prev_r_placed
                bridge_c = c
                bridge_cell = grid.cell(bridge_r, bridge_c)
                if bridge_cell is not None and bridge_cell.is_land and not bridge_cell.is_road and not bridge_cell.is_water:
                    bridge_cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
                    path.append((bridge_r, bridge_c))

        cell = grid.cell(r, c)
        if cell is not None and cell.is_land and not cell.is_water:
            if not cell.is_road:
                cell.set_road('road_1010', ROAD_CONNECTOR, variation=0)
                path.append((r, c))
            prev_r_placed = r
            prev_c_placed = c

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

    # Each diagonal gets a unique seed-dependent start in the NW quadrant
    # and a unique end in the SE quadrant, so diagonals differ every seed.
    start_frac_r = rng.uniform(0.05 + index * 0.12, 0.25 + index * 0.10)
    start_frac_c = rng.uniform(0.05 + index * 0.08, 0.25 + index * 0.08)
    end_frac_r   = rng.uniform(0.75 - index * 0.05, 0.95)
    end_frac_c   = rng.uniform(0.75 - index * 0.05, 0.95)
    start_r = max(1, int(rows * start_frac_r))
    start_c = max(1, int(cols * start_frac_c))
    end_r   = min(rows - 2, int(rows * end_frac_r))
    end_c   = min(cols - 2, int(cols * end_frac_c))

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

        if bin(grid.road_bitmask(r, c)).count('1') < 3:
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


# ── Zone-score helper ─────────────────────────────────────────────────────────

def _zone_score(pos: int, total: int) -> float:
    """Return 0.0 (map center / CBD) to 1.0 (map edge / residential)."""
    return abs(pos - total / 2) / (total / 2)


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

    # Base drift: connector_turn_bias=0.05 → 1 (CBD straight); higher values
    # give more organic outer streets.  Per-street zone scaling is applied below.
    drift_max = max(1, round(config.connector_turn_bias * 20))

    # ── Grid line positions ───────────────────────────────────────────────────
    ns_bases = list(range(av_block, cols - av_block // 2, av_block))
    ew_bases = list(range(cs_block, rows - cs_block // 2, cs_block))

    if not ns_bases and not ew_bases:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 1.0,
            'Grid too small for street layout at current block sizes.'
        )
        return

    # Unit 9 — Noise-offset jitter: shift each street position by up to ±25% of
    # the block spacing so block widths vary naturally without breaking connectivity.
    min_sep = max(config.min_block_depth + 1, 2)

    jittered_ns: list[int] = []
    seen_ns: set[int] = set()
    for base_col in ns_bases:
        jitter = int(noise2d(base_col / max(cols, 1) * 3.0, 0.5, perm) * av_block * 0.25)
        jittered = max(2, min(cols - 2, base_col + jitter))
        if jittered not in seen_ns:
            jittered_ns.append(jittered)
            seen_ns.add(jittered)
    ns_bases = sorted(jittered_ns)

    jittered_ew: list[int] = []
    seen_ew: set[int] = set()
    for base_row in ew_bases:
        jitter = int(noise2d(base_row / max(rows, 1) * 3.0, 1.5, perm) * cs_block * 0.25)
        jittered = max(2, min(rows - 2, base_row + jitter))
        if jittered not in seen_ew:
            jittered_ew.append(jittered)
            seen_ew.add(jittered)
    ew_bases = sorted(jittered_ew)

    # Apply zone-aware density: CBD center is denser, residential edges sparser.
    # Coastal maps have less land area — scale down density proportionally so
    # road% stays within 15–35% regardless of how much land the coastline removed.
    land_cells = sum(1 for _, _, cell in grid.all_cells() if cell.is_land)
    total_cells_map = rows * cols
    land_fraction = land_cells / total_cells_map if total_cells_map > 0 else 1.0
    # coast_factor: 1.0 for fully inland maps; reduces toward ~0.75 for 50% coastal
    coast_factor = min(1.0, land_fraction / 0.72)

    rng.shuffle(ns_bases)
    rng.shuffle(ew_bases)

    ns_bases_kept = []
    for base_col in ns_bases:
        zone = _zone_score(base_col, cols)
        eff_density = config.connector_density * (1.0 - zone * 0.35) * coast_factor
        if rng.random() < eff_density:
            ns_bases_kept.append(base_col)
    # Guarantee at least half the candidate streets are placed (prevents degenerate grids)
    min_ns = max(1, (len(ns_bases) + 1) // 2)
    if len(ns_bases_kept) < min_ns:
        ns_bases_kept = list(ns_bases[:min_ns])
    ns_bases = sorted(ns_bases_kept)

    ew_bases_kept = []
    for base_row in ew_bases:
        zone = _zone_score(base_row, rows)
        eff_density = config.connector_density * (1.0 - zone * 0.50) * coast_factor
        if rng.random() < eff_density:
            ew_bases_kept.append(base_row)
    # Guarantee at least half the candidate streets are placed
    min_ew = max(1, (len(ew_bases) + 1) // 2)
    if len(ew_bases_kept) < min_ew:
        ew_bases_kept = list(ew_bases[:min_ew])
    ew_bases = sorted(ew_bases_kept)

    total_streets = len(ns_bases) + len(ew_bases)
    total_cells   = 0
    streets_done  = 0

    yield GeneratorProgress(
        PHASE_CONNECTOR, 0.02,
        f'Harlem grid: {len(ns_bases)} avenues (±{av_block}px) '
        f'+ {len(ew_bases)} cross-streets (±{cs_block}px), drift=±{drift_max}'
    )

    # ── Perimeter streets (guaranteed, added after density filter) ────────────
    # Run one guaranteed N-S avenue near each horizontal edge and one guaranteed
    # E-W cross-street near each vertical edge.  These create enclosed
    # residential blocks at the map periphery.
    # Only placed on maps large enough to benefit (≥48 cells per axis).
    # Coastal-side perimeter streets are skipped to avoid isolated fragments
    # where water gaps prevent NS/EW connectivity.
    min_sep_p = max(config.min_block_depth + 2, 4)
    coast = config.coast_side

    perimeter_ns: list[int] = []
    if cols >= 48:
        for perim_col, coast_skip in ((3, 'west'), (cols - 4, 'east')):
            if coast == coast_skip:
                continue           # skip the coastal side
            if 2 <= perim_col <= cols - 3:
                if all(abs(perim_col - b) >= min_sep_p for b in ns_bases):
                    perimeter_ns.append(perim_col)

    perimeter_ew: list[int] = []
    if rows >= 48:
        for perim_row, coast_skip in ((3, 'north'), (rows - 4, 'south')):
            if coast == coast_skip:
                continue           # skip the coastal side
            if 2 <= perim_row <= rows - 3:
                if all(abs(perim_row - b) >= min_sep_p for b in ew_bases):
                    perimeter_ew.append(perim_row)

    # ── Pass 1: N-S avenues ───────────────────────────────────────────────────
    for base_col in ns_bases:
        zone          = _zone_score(base_col, cols)
        street_drift  = max(1, drift_max + int(zone * 2))
        path          = _trace_ns_street(grid, base_col, perm, street_drift)
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
        zone          = _zone_score(base_row, rows)
        street_drift  = max(1, drift_max + int(zone * 2))
        path          = _trace_ew_street(grid, base_row, perm, street_drift)
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
    # Include perimeter streets so gap-fill doesn't double-fill areas near perimeter.
    all_ns_for_gap = sorted(set(ns_bases) | set(perimeter_ns))
    all_ew_for_gap = sorted(set(ew_bases) | set(perimeter_ew))
    sec_ns = _gap_fill_positions(all_ns_for_gap, 0, cols - 1, av_block, rng, probability=0.45)
    sec_ew = _gap_fill_positions(all_ew_for_gap, 0, rows - 1, cs_block, rng, probability=0.45)

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

    # ── Pass 2.6: Guaranteed perimeter streets ────────────────────────────────
    # Placed with drift_max=0 (straight) at exactly the perimeter column/row to
    # guarantee cardinal connectivity with all cross-streets.
    perim_cells = 0
    for base_col in perimeter_ns:
        path = _trace_ns_street(grid, base_col, perm, 0)
        perim_cells += len(path)
        total_cells += len(path)
    for base_row in perimeter_ew:
        path = _trace_ew_street(grid, base_row, perm, 0)
        perim_cells += len(path)
        total_cells += len(path)

    if perim_cells > 0:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 0.67,
            f'Perimeter streets: {len(perimeter_ns)} NS + {len(perimeter_ew)} EW '
            f'({perim_cells} cells)'
        )

    # ── Pass 3.5: Connectivity repair ────────────────────────────────────────
    # Find all connected road components; keep the LARGEST one and remove the
    # rest.  Starting BFS from all_road_cells[0] was a bug: on coastal maps the
    # first road cell (by row-major scan) can be in a small peninsula fragment,
    # causing the entire main road network to be wrongly classified as isolated.
    all_road_cells = [(r, c) for r, c, cell in grid.all_cells() if cell.is_road]
    if all_road_cells:
        from ..constants import TILE_GROUND_LAND
        unvisited: set[tuple[int, int]] = set(all_road_cells)
        components: list[set[tuple[int, int]]] = []

        while unvisited:
            start = next(iter(unvisited))
            comp: set[tuple[int, int]] = set()
            stack: list[tuple[int, int]] = [start]
            while stack:
                r2, c2 = stack.pop()
                if (r2, c2) in comp:
                    continue
                comp.add((r2, c2))
                for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr2, nc2 = r2 + dr2, c2 + dc2
                    if (
                        grid.in_bounds(nr2, nc2)
                        and grid[nr2][nc2].is_road
                        and (nr2, nc2) not in comp
                    ):
                        stack.append((nr2, nc2))
            components.append(comp)
            unvisited -= comp

        largest = max(components, key=len)
        isolated_removed = 0
        for r2, c2 in all_road_cells:
            if (r2, c2) not in largest:
                cell2 = grid[r2][c2]
                cell2.clear_road()
                cell2.set_ground(TILE_GROUND_LAND)
                isolated_removed += 1

        if isolated_removed > 0:
            yield GeneratorProgress(
                PHASE_CONNECTOR, 0.68,
                f'Connectivity repair: removed {isolated_removed} isolated road cells '
                f'({len(components)} components → kept largest with {len(largest)} cells).'
            )

    # ── Pass 3.6: Dead-end stub pruning ──────────────────────────────────────
    # Walk every road dead-end (1 road neighbour); trace the linear stub.
    # Stubs longer than _MAX_STUB_CELLS are pruned (reverted to land) —
    # they block lot subdivision without providing useful connectivity.
    # Deliberate cul-de-sacs (max 6 cells by design) are preserved.
    _MAX_STUB_CELLS = 6
    pruned_stubs = 0
    pruned_cells = 0

    # Iteratively prune: removing a stub tip may create a new dead end.
    for _prune_pass in range(8):
        tips = [
            (r2, c2)
            for r2, c2, cell2 in grid.all_cells()
            if cell2.is_road
            and sum(
                1 for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if grid.in_bounds(r2 + dr2, c2 + dc2) and grid[r2 + dr2][c2 + dc2].is_road
            ) == 1
        ]
        if not tips:
            break

        found_long = False
        for tip in tips:
            # Trace stub from tip back to the junction
            visited_s: list[tuple[int, int]] = [tip]
            cur = tip
            while True:
                r2, c2 = cur
                nexts = [
                    (r2 + dr2, c2 + dc2)
                    for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    if grid.in_bounds(r2 + dr2, c2 + dc2)
                    and grid[r2 + dr2][c2 + dc2].is_road
                    and (r2 + dr2, c2 + dc2) not in visited_s
                ]
                if len(nexts) == 1:
                    visited_s.append(nexts[0])
                    cur = nexts[0]
                else:
                    break  # reached junction or isolated (stop)
            if len(visited_s) > _MAX_STUB_CELLS:
                # Prune the stub (keep the junction cell)
                from ..constants import TILE_GROUND_LAND
                for sr, sc in visited_s[:-1]:  # all except the junction endpoint
                    cell2 = grid[sr][sc]
                    cell2.clear_road()
                    cell2.set_ground(TILE_GROUND_LAND)
                    pruned_cells += 1
                pruned_stubs += 1
                found_long = True
        if not found_long:
            break

    if pruned_stubs > 0:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 0.69,
            f'Stub pruning: removed {pruned_stubs} long dead-ends ({pruned_cells} cells).'
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

    # ── Passes 4 / 4b / 4c: bitmask resolution, surface variation, cul-de-sacs ─
    # Single scan covers all three tasks to avoid triple-iterating the grid.
    yield GeneratorProgress(PHASE_CONNECTOR, 0.72, 'Resolving road tile variants …')

    cul_de_sac_count = 0
    for r, c, cell in grid.all_cells():
        if not cell.is_road:
            continue
        tile_id = cell.layers[LAYER_ROAD] or ''
        if tile_id.startswith('roundabout_'):
            continue

        # Pass 4: resolve bitmask tile ID
        mask    = grid.road_bitmask(r, c)
        tile_id = REGISTRY.resolve_road_tile_id(mask, cell.road_category)
        cell.layers[LAYER_ROAD] = tile_id

        if cell.road_category != ROAD_CONNECTOR:
            continue

        # Pass 4b: randomise surface variant per connector cell
        variants = REGISTRY.get_variants(tile_id)
        # (variation field removed in Sprint 5 — sprite renderer picks variants via tile_id)

        # Pass 4c: cul-de-sac sprouting — residential cells on through-roads only
        if cell.zone_id != ZONE_RESIDENTIAL:
            continue
        popcount = bin(mask).count('1')
        if popcount != 2:
            continue
        if rng.random() > 0.15:
            continue

        connected_dirs = [d for d, bit in zip(range(4), [8, 4, 2, 1]) if mask & bit]
        perp_dirs = [d for d in range(4) if d not in connected_dirs]

        for perp_dir in rng.sample(perp_dirs, min(len(perp_dirs), 2)):
            off_r, off_c = DIRECTION_OFFSETS[perp_dir]
            branch_len = rng.randint(3, 6)
            branch = []
            br, bc = r + off_r, c + off_c
            ok = True
            for _ in range(branch_len):
                nbr = grid.cell(br, bc)
                if nbr is None or nbr.is_water or nbr.is_road:
                    ok = False
                    break
                branch.append((br, bc))
                br += off_r
                bc += off_c

            if ok and len(branch) >= 3:
                for sr, sc in branch:
                    grid[sr][sc].set_road('road_1010', ROAD_CONNECTOR, variation=0)
                # Re-resolve bitmask for every new cul-de-sac cell and its
                # immediate neighbour (the junction cell that spawned this branch).
                for sr, sc in branch:
                    mask = grid.road_bitmask(sr, sc)
                    tid = REGISTRY.resolve_road_tile_id(mask, ROAD_CONNECTOR)
                    grid[sr][sc].layers[LAYER_ROAD] = tid
                # Re-resolve the junction cell that now has a new branch connection
                mask = grid.road_bitmask(r, c)
                tid = REGISTRY.resolve_road_tile_id(mask, cell.road_category)
                cell.layers[LAYER_ROAD] = tid
                cul_de_sac_count += 1
                break

    if cul_de_sac_count > 0:
        yield GeneratorProgress(
            PHASE_CONNECTOR, 0.90,
            f'Cul-de-sac stubs: {cul_de_sac_count} residential dead-ends added.'
        )

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
        popcount = bin(grid.road_bitmask(r, c)).count('1')
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
