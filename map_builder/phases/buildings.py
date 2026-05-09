"""
map_builder/phases/buildings.py
────────────────────────────────
Phase 9 — RPG Building Assignment & Game Data Layer

This phase transforms the structural city data (blocks, lots, parks, zones)
into a fully game-ready tile set by assigning:

  • tile_role   : traversability class (ROLE_* constants)
  • building_type : semantic building label (BLDG_* constants) for each lot
  • encounter_chance : per-cell random encounter probability (0.0–1.0)
  • is_spawn_point : True on cells chosen as NPC/enemy origin points
  • landmark_type : named landmark at key positions (station, hospital, …)

Design rules (from Team 1 / Team 2 research):
  Roads & sidewalks → walkable, low-medium encounter
  Park cells        → walkable, higher encounter (grass/nature)
  Lot cells         → obstacle (buildings), encounter = 0
  Exterior land     → void/obstacle, encounter = 0
  Water             → impassable, encounter = 0

Landmark injection:
  civic_anchor lot      → BLDG_CIVIC_HALL + landmark 'town_hall'
  Nearest highway×highway junction to CBD → landmark 'station'
  Largest Midtown lot   → BLDG_HOSPITAL + landmark 'hospital'
  Midtown lot near CBD edge → BLDG_POLICE + landmark 'police'

Spawn point rules:
  • One spawn point per 25 road cells in Residential (enemy spawns)
  • One spawn point per 10 road cells in CBD/Midtown (NPC spawns)
  • All park cells have is_spawn_point = True (high encounter zones)
"""
from __future__ import annotations
import random
from typing import Generator

from ..constants import (
    PHASE_BUILDINGS, SALT_BUILDINGS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    ROLE_WALKABLE_HIGHWAY, ROLE_WALKABLE_ROAD, ROLE_WALKABLE_ALLEY,
    ROLE_WALKABLE_SIDEWALK, ROLE_WALKABLE_PARK, ROLE_WALKABLE_PLAZA,
    ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN, ROLE_BUILDING_RESI,
    ROLE_BUILDING_CIVIC, ROLE_WATER, ROLE_EXTERIOR,
    BLDG_OFFICE, BLDG_BANK, BLDG_MARKET, BLDG_CIVIC_HALL,
    BLDG_SHOP, BLDG_RESTAURANT, BLDG_APARTMENT, BLDG_CLINIC,
    BLDG_HOUSE, BLDG_SCHOOL, BLDG_PARK_FEATURE, BLDG_STATION,
    BLDG_HOSPITAL, BLDG_POLICE, BLDG_EMPTY_LOT,
    CBD_BLDG_WEIGHTS, MIDTOWN_BLDG_WEIGHTS, RESI_BLDG_WEIGHTS, WATERFRONT_BLDG_WEIGHTS,
    ENCOUNTER_BASE, ENCOUNTER_ZONE_MOD,
    ENCOUNTER_DENSITY_K, ENCOUNTER_CIVIC_PENALTY, ENCOUNTER_CIVIC_RADIUS,
    BLOCK_EXTERIOR_ID,
    LAYER_ROAD,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress


# ── Encounter chance calculator (research-grade formula) ──────────────────────

def _compute_encounter(
    base: float,
    cell,
    row: int,
    col: int,
    civic_pos: tuple[int, int] | None,
) -> float:
    """
    Research-grade encounter probability formula (Team 2/5 report §2.5).

    chance = clamp( (base + density_bonus) * zone_mult + zone_offset
                    - civic_penalty, 0.0, 1.0 )
    """
    density_bonus = ENCOUNTER_DENSITY_K * cell.density_score
    zone_mult, zone_off = ENCOUNTER_ZONE_MOD.get(cell.zone_id, (1.0, 0.0))
    chance = (base + density_bonus) * zone_mult + zone_off

    if civic_pos is not None:
        dist = max(abs(row - civic_pos[0]), abs(col - civic_pos[1]))
        if dist <= ENCOUNTER_CIVIC_RADIUS:
            chance -= ENCOUNTER_CIVIC_PENALTY

    return round(max(0.0, min(1.0, chance)), 3)


# ── Weighted random choice helper ─────────────────────────────────────────────

def _weighted_choice(rng: random.Random, weights: list) -> str:
    """Pick a building type from a [(type, weight), …] list."""
    total = sum(w for _, w in weights)
    r = rng.uniform(0, total)
    cumul = 0
    for btype, w in weights:
        cumul += w
        if r <= cumul:
            return btype
    return weights[-1][0]


# ── Landmark placement ────────────────────────────────────────────────────────

_LANDMARK_MIN_SEPARATION = 6   # minimum Chebyshev distance between any two landmarks


def _landmarks_too_close(
    pos: tuple[int, int],
    placed_positions: list[tuple[int, int]],
    min_dist: int = _LANDMARK_MIN_SEPARATION,
) -> bool:
    """Return True if pos is within min_dist Chebyshev of any placed landmark."""
    return any(
        max(abs(pos[0] - p[0]), abs(pos[1] - p[1])) < min_dist
        for p in placed_positions
    )


def _inject_landmarks(
    grid:    MapGrid,
    blocks:  list,
    lots:    list,
    civic:   tuple | None,
    rng:     random.Random,
) -> dict:
    """
    Assign landmark_type to specific lots/cells. Returns info dict.
    Returns dict of landmark_type → (row, col) placed.
    Landmarks are separated by at least _LANDMARK_MIN_SEPARATION Chebyshev cells.
    """
    placed: dict[str, tuple[int, int]] = {}
    placed_positions: list[tuple[int, int]] = []
    rows, cols = grid.height, grid.width

    # ── Town Hall at civic anchor lot ─────────────────────────────────────────
    if civic:
        cr, cc = civic
        anchor_cell = grid[cr][cc]
        anchor_cell.landmark_type = 'town_hall'
        anchor_cell.building_type = BLDG_CIVIC_HALL
        anchor_cell.tile_role = ROLE_BUILDING_CIVIC
        # Spread the civic hall across the whole lot using lots list.
        # If the civic anchor lot is too large, only mark the anchor cell
        # itself plus adjacent cells (cap at 12 cells for visual clarity).
        anchor_lot_id = anchor_cell.lot_id
        if anchor_lot_id >= 0:
            for lot_cells in lots:
                if not lot_cells:
                    continue
                r0, c0 = next(iter(lot_cells))
                if grid[r0][c0].lot_id == anchor_lot_id:
                    # Cap lot coverage at 12 cells for large lots
                    cells_to_mark = list(lot_cells)[:12]
                    for r, c in cells_to_mark:
                        grid[r][c].landmark_type = 'town_hall'
                        grid[r][c].building_type = BLDG_CIVIC_HALL
                        grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                    break
        placed['town_hall'] = (cr, cc)
        placed_positions.append((cr, cc))

    # ── Train station: highway × highway junction closest to CBD center ───────
    hw_junctions = [
        (r, c) for r, c, cell in grid.all_cells()
        if cell.is_road and cell.road_category == ROAD_HIGHWAY
        and cell.zone_id in (ZONE_CBD, ZONE_MIDTOWN)
    ]
    if hw_junctions:
        cr_c = rows / 2.0
        cc_c = cols / 2.0
        station_cell_rc = min(
            hw_junctions,
            key=lambda rc: (rc[0] - cr_c) ** 2 + (rc[1] - cc_c) ** 2,
        )
        # Find the lot nearest to this junction
        sr, sc = station_cell_rc
        nearest_lot = _nearest_lot_of_zone(grid, sr, sc, ZONE_MIDTOWN, radius=max(rows, cols))
        if nearest_lot is not None and not _landmarks_too_close(nearest_lot, placed_positions):
            target_lot_id = grid[nearest_lot[0]][nearest_lot[1]].lot_id
            if target_lot_id >= 0:
                for lot_cells in lots:
                    if not lot_cells:
                        continue
                    r0, c0 = next(iter(lot_cells))
                    if grid[r0][c0].lot_id == target_lot_id:
                        for r, c in lot_cells:
                            grid[r][c].landmark_type = 'station'
                            grid[r][c].building_type = BLDG_STATION
                            grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                        break
            placed['station'] = nearest_lot
            placed_positions.append(nearest_lot)

    # ── Hospital: largest Midtown lot far from CBD center ─────────────────────
    # Hospital: pick a medium Midtown lot (8-20 cells) — large enough to notice,
    # small enough not to dominate the visual with civic colour.
    midtown_lots = _lots_by_zone(grid, lots, ZONE_MIDTOWN)
    if midtown_lots:
        # Sort by size, prefer 8-20 cell lots (realistic hospital footprint)
        midtown_lots.sort(key=lambda cells: abs(len(cells) - 14))
        for lot_cells in midtown_lots[:8]:
            if not (5 <= len(lot_cells) <= 22):
                continue
            r0, c0 = next(iter(lot_cells))
            cell0 = grid[r0][c0]
            if not cell0.landmark_type and not _landmarks_too_close((r0, c0), placed_positions):
                for r, c in lot_cells:
                    grid[r][c].landmark_type = 'hospital'
                    grid[r][c].building_type = BLDG_HOSPITAL
                    grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                placed['hospital'] = (r0, c0)
                placed_positions.append((r0, c0))
                break

    # ── Police station: small-medium Midtown lot near CBD boundary ────────────
    boundary_lots = _lots_by_zone(grid, lots, ZONE_MIDTOWN, near_zone=ZONE_CBD, radius=5)
    if boundary_lots:
        # Prefer compact police station (4-12 cells)
        boundary_lots.sort(key=lambda cells: abs(len(cells) - 8))
        for lot_cells in boundary_lots[:10]:
            if len(lot_cells) > 15:
                continue
            r0, c0 = next(iter(lot_cells))
            cell0 = grid[r0][c0]
            if not cell0.landmark_type and not _landmarks_too_close((r0, c0), placed_positions):
                for r, c in lot_cells:
                    grid[r][c].landmark_type = 'police'
                    grid[r][c].building_type = BLDG_POLICE
                    grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                placed['police'] = (r0, c0)
                placed_positions.append((r0, c0))
                break

    # ── School: medium Residential lot, ensures landmark spread to outer zone ──
    resi_lots = _lots_by_zone(grid, lots, ZONE_RESIDENTIAL)
    if resi_lots:
        # Prefer 6-16 cell lots — realistic school footprint
        resi_lots.sort(key=lambda cells: abs(len(cells) - 10))
        for lot_cells in resi_lots[:12]:
            if not (5 <= len(lot_cells) <= 20):
                continue
            r0, c0 = next(iter(lot_cells))
            cell0 = grid[r0][c0]
            if not cell0.landmark_type and not _landmarks_too_close((r0, c0), placed_positions):
                for r, c in lot_cells:
                    grid[r][c].landmark_type = 'school'
                    grid[r][c].building_type = BLDG_SCHOOL
                    grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                placed['school'] = (r0, c0)
                placed_positions.append((r0, c0))
                break

    return placed


def _nearest_lot_of_zone(
    grid: MapGrid, r0: int, c0: int, zone: int, radius: int
) -> tuple[int, int] | None:
    for d in range(1, radius + 1):
        for dr in range(-d, d + 1):
            for dc in range(-d, d + 1):
                if max(abs(dr), abs(dc)) != d:
                    continue
                r, c = r0 + dr, c0 + dc
                if grid.in_bounds(r, c):
                    cell = grid[r][c]
                    if cell.zone_id == zone and cell.lot_id >= 0 and not cell.is_park:
                        return (r, c)
    return None


def _lots_by_zone(
    grid: MapGrid, lots: list, zone: int,
    near_zone: int | None = None, radius: int = 0,
) -> list[set]:
    result = []
    for lot_cells in lots:
        if not lot_cells:
            continue
        r0, c0 = next(iter(lot_cells))
        cell0 = grid[r0][c0]
        if cell0.zone_id != zone:
            continue
        if near_zone is not None:
            # Check if any cell in lot is within radius of near_zone
            found = False
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    nr, nc = r0 + dr, c0 + dc
                    if grid.in_bounds(nr, nc) and grid[nr][nc].zone_id == near_zone:
                        found = True
                        break
                if found:
                    break
            if not found:
                continue
        result.append(lot_cells)
    return result


# ── Waterfront detection ─────────────────────────────────────────────────────

def _is_waterfront_lot(grid, lot_cells) -> bool:
    """Return True if any cell in the lot is adjacent to a water cell."""
    for r, c in lot_cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nbr = grid.cell(r + dr, c + dc)
            if nbr is not None and nbr.is_water:
                return True
    return False


# ── Alley vs cul-de-sac length check ─────────────────────────────────────────

def _dead_end_length(grid, r: int, c: int) -> int:
    """BFS walk from dead-end cell; count connected single-width path length."""
    visited = {(r, c)}
    current = (r, c)
    length = 1
    while True:
        nbrs = [
            (r2, c2)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            for r2, c2 in [(current[0] + dr, current[1] + dc)]
            if grid.in_bounds(r2, c2) and grid[r2][c2].is_road
            and (r2, c2) not in visited
        ]
        if len(nbrs) == 1:
            visited.add(nbrs[0])
            current = nbrs[0]
            length += 1
        else:
            break
    return length


# ── Main phase generator ──────────────────────────────────────────────────────

def generate_buildings(
    grid:   MapGrid,
    config: MapConfig,
    blocks: list,
    lots:   list,
    civic:  tuple | None = None,
) -> Generator[GeneratorProgress, None, None]:
    """
    Phase 9 — RPG Building Assignment.

    Assigns tile_role, building_type, encounter_chance, is_spawn_point,
    and landmark_type to every cell in the grid.
    """
    yield GeneratorProgress(PHASE_BUILDINGS, 0.0, 'Assigning RPG tile roles …')

    rng = random.Random(config.master_seed ^ SALT_BUILDINGS)
    rows, cols = grid.height, grid.width
    total_cells = rows * cols

    # ── Pre-compute alley cells: connectors with road-bitmask pop-count == 1 ──
    # A dead-end connector (only one neighbour road) = potential alley/cul-de-sac.
    # Short dead-ends (length ≤ 3) = service alley; longer = cul-de-sac (normal road).
    alley_cells: set[tuple[int, int]] = set()
    for r, c, cell in grid.all_cells():
        if cell.is_road and cell.road_category == ROAD_CONNECTOR:
            tile_id = cell.layers.get(LAYER_ROAD) or ''
            if not tile_id.startswith('roundabout_'):
                bitmask = grid.road_bitmask(r, c)
                if bin(bitmask).count('1') == 1:
                    if _dead_end_length(grid, r, c) <= 3:
                        alley_cells.add((r, c))

    # ── Pre-compute plaza cells: roundabout tiles ─────────────────────────────
    plaza_cells: set[tuple[int, int]] = set()
    for r, c, cell in grid.all_cells():
        if cell.is_road:
            tile_id = cell.layers.get(LAYER_ROAD) or ''
            if tile_id.startswith('roundabout_'):
                plaza_cells.add((r, c))

    # ── Pass 1: assign tile_role and research-grade encounter_chance ──────────
    civic_pos = civic  # (row, col) or None

    for r, c, cell in grid.all_cells():
        if cell.is_water:
            cell.tile_role = ROLE_WATER
            cell.encounter_chance = 0.0

        elif cell.is_road:
            # Determine precise road role
            if (r, c) in plaza_cells:
                cell.tile_role = ROLE_WALKABLE_PLAZA
                cell.encounter_chance = 0.0   # scripted encounters only
            elif (r, c) in alley_cells:
                cell.tile_role = ROLE_WALKABLE_ALLEY
                base = ENCOUNTER_BASE.get(ROLE_WALKABLE_ALLEY, 0.30)
                cell.encounter_chance = _compute_encounter(
                    base, cell, r, c, civic_pos
                )
                cell.is_spawn_point = True
            elif cell.road_category == ROAD_HIGHWAY:
                cell.tile_role = ROLE_WALKABLE_HIGHWAY
                base = ENCOUNTER_BASE.get(ROLE_WALKABLE_HIGHWAY, 0.08)
                cell.encounter_chance = _compute_encounter(
                    base, cell, r, c, civic_pos
                )
            else:
                cell.tile_role = ROLE_WALKABLE_ROAD
                base = ENCOUNTER_BASE.get(ROLE_WALKABLE_ROAD, 0.12)
                cell.encounter_chance = _compute_encounter(
                    base, cell, r, c, civic_pos
                )

        elif cell.is_park:
            # Parks take priority over sidewalk — small blocks are fully covered
            # by sidewalk adjacency and must still read as green open space
            cell.tile_role = ROLE_WALKABLE_PARK
            base = ENCOUNTER_BASE.get(ROLE_WALKABLE_PARK, 0.25)
            cell.encounter_chance = _compute_encounter(
                base, cell, r, c, civic_pos
            )
            cell.is_spawn_point = True

        elif cell.is_sidewalk:
            cell.tile_role = ROLE_WALKABLE_SIDEWALK
            base = ENCOUNTER_BASE.get(ROLE_WALKABLE_SIDEWALK, 0.05)
            cell.encounter_chance = _compute_encounter(
                base, cell, r, c, civic_pos
            )

        elif cell.lot_id >= 0:
            # Setback cells keep their sidewalk role; skip building assignment
            if getattr(cell, 'is_setback', False):
                # Setback cells adjacent to a park get park-adjacent flag for
                # visual rendering (use park colour instead of lawn).
                for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nbr2 = grid.cell(r + dr2, c + dc2)
                    if nbr2 is not None and nbr2.is_park:
                        cell.near_park = True
                        break
                cell.encounter_chance = 0.0
                continue
            if cell.zone_id == ZONE_CBD:
                cell.tile_role = ROLE_BUILDING_CBD
            elif cell.zone_id == ZONE_MIDTOWN:
                cell.tile_role = ROLE_BUILDING_MIDTOWN
            else:
                cell.tile_role = ROLE_BUILDING_RESI
            cell.encounter_chance = 0.0

        else:
            cell.tile_role = ROLE_EXTERIOR
            cell.encounter_chance = 0.0

    yield GeneratorProgress(PHASE_BUILDINGS, 0.25, 'Tile roles assigned. Assigning building types …')

    # ── Pass 2: assign building types to lots ─────────────────────────────────
    # Use lot_cells lists directly — O(total_cells) total, not O(lots × cells)
    for lot_cells in lots:
        if not lot_cells:
            continue
        r0, c0 = next(iter(lot_cells))
        zone = grid[r0][c0].zone_id

        # Waterfront lots override zone weights with coastal building mix
        if _is_waterfront_lot(grid, lot_cells):
            btype = _weighted_choice(rng, WATERFRONT_BLDG_WEIGHTS)
        elif zone == ZONE_CBD:
            btype = _weighted_choice(rng, CBD_BLDG_WEIGHTS)
        elif zone == ZONE_MIDTOWN:
            btype = _weighted_choice(rng, MIDTOWN_BLDG_WEIGHTS)
        else:
            btype = _weighted_choice(rng, RESI_BLDG_WEIGHTS)

        # Assign directly to cells in this lot; skip setback cells (they stay as sidewalk)
        for r, c in lot_cells:
            if getattr(grid[r][c], 'is_setback', False):
                continue
            grid[r][c].building_type = btype

    yield GeneratorProgress(PHASE_BUILDINGS, 0.50, 'Building types assigned. Injecting landmarks …')

    # ── Pass 3: landmark injection ────────────────────────────────────────────
    landmarks = _inject_landmarks(grid, blocks, lots, civic, rng)

    yield GeneratorProgress(
        PHASE_BUILDINGS, 0.65,
        f'Landmarks placed: {list(landmarks.keys())}. Placing spawn points …',
    )

    # ── Pass 4: spawn points on roads ─────────────────────────────────────────
    # CBD/Midtown: 1 spawn per 10 road cells (NPC spawns)
    # Residential: 1 spawn per 25 road cells (enemy spawns)
    road_cells_by_zone: dict[int, list[tuple[int, int]]] = {
        ZONE_CBD: [], ZONE_MIDTOWN: [], ZONE_RESIDENTIAL: [],
    }
    for r, c, cell in grid.all_cells():
        if cell.is_road and cell.road_category == ROAD_CONNECTOR:
            zone = cell.zone_id
            if zone in road_cells_by_zone:
                road_cells_by_zone[zone].append((r, c))

    spawn_count = 0
    for zone, road_list in road_cells_by_zone.items():
        rng.shuffle(road_list)
        interval = 10 if zone in (ZONE_CBD, ZONE_MIDTOWN) else 25
        for i, (r, c) in enumerate(road_list):
            if i % interval == 0:
                grid[r][c].is_spawn_point = True
                spawn_count += 1

    # ── Pass 5: Alley terminus encounter boost ────────────────────────────────
    # Cells within Chebyshev distance 2 of an alley dead-end get a small
    # encounter-chance boost (dark alleyway atmosphere spills onto nearby road).
    ALLEY_BOOST = 0.07
    alley_tips: list[tuple[int, int]] = [
        (r, c)
        for r, c, cell in grid.all_cells()
        if cell.tile_role == ROLE_WALKABLE_ALLEY
        and sum(
            1
            for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if grid.in_bounds(r + dr2, c + dc2) and grid[r + dr2][c + dc2].is_road
        ) == 1
    ]
    for ar, ac in alley_tips:
        for dr2 in range(-2, 3):
            for dc2 in range(-2, 3):
                if max(abs(dr2), abs(dc2)) > 2:
                    continue
                nbr = grid.cell(ar + dr2, ac + dc2)
                if nbr is not None and nbr.tile_role in (
                    ROLE_WALKABLE_ROAD, ROLE_WALKABLE_HIGHWAY, ROLE_WALKABLE_SIDEWALK
                ):
                    nbr.encounter_chance = round(
                        min(1.0, nbr.encounter_chance + ALLEY_BOOST), 3
                    )

    yield GeneratorProgress(
        PHASE_BUILDINGS, 1.0,
        (
            f'Buildings phase complete — {len(lots)} lots typed, '
            f'{len(landmarks)} landmarks, {spawn_count} spawn points, '
            f'{len(alley_tips)} alley tips boosted.'
        ),
    )