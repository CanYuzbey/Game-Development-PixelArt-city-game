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
    CBD_BLDG_WEIGHTS, MIDTOWN_BLDG_WEIGHTS, RESI_BLDG_WEIGHTS,
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
    """
    placed: dict[str, tuple[int, int]] = {}
    rows, cols = grid.height, grid.width

    # ── Town Hall at civic anchor lot ─────────────────────────────────────────
    if civic:
        cr, cc = civic
        anchor_cell = grid[cr][cc]
        anchor_cell.landmark_type = 'town_hall'
        anchor_cell.building_type = BLDG_CIVIC_HALL
        anchor_cell.tile_role = ROLE_BUILDING_CIVIC
        # Spread the civic hall across the whole lot using lots list
        anchor_lot_id = anchor_cell.lot_id
        if anchor_lot_id >= 0:
            for lot_cells in lots:
                if not lot_cells:
                    continue
                r0, c0 = next(iter(lot_cells))
                if grid[r0][c0].lot_id == anchor_lot_id:
                    for r, c in lot_cells:
                        grid[r][c].landmark_type = 'town_hall'
                        grid[r][c].building_type = BLDG_CIVIC_HALL
                        grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                    break
        placed['town_hall'] = (cr, cc)

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
        nearest_lot = _nearest_lot_of_zone(grid, sr, sc, ZONE_MIDTOWN, radius=8)
        if nearest_lot is not None:
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

    # ── Hospital: largest Midtown lot far from CBD center ─────────────────────
    midtown_lots = _lots_by_zone(grid, lots, ZONE_MIDTOWN)
    if midtown_lots:
        midtown_lots.sort(key=lambda cells: len(cells), reverse=True)
        for lot_cells in midtown_lots[:5]:
            r0, c0 = next(iter(lot_cells))
            cell0 = grid[r0][c0]
            if not cell0.landmark_type:
                for r, c in lot_cells:
                    grid[r][c].landmark_type = 'hospital'
                    grid[r][c].building_type = BLDG_HOSPITAL
                    grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                placed['hospital'] = (r0, c0)
                break

    # ── Police station: Midtown lot near CBD/Midtown boundary ─────────────────
    boundary_lots = _lots_by_zone(grid, lots, ZONE_MIDTOWN, near_zone=ZONE_CBD, radius=5)
    if boundary_lots:
        rng.shuffle(boundary_lots)
        for lot_cells in boundary_lots[:8]:
            r0, c0 = next(iter(lot_cells))
            cell0 = grid[r0][c0]
            if not cell0.landmark_type:
                for r, c in lot_cells:
                    grid[r][c].landmark_type = 'police'
                    grid[r][c].building_type = BLDG_POLICE
                    grid[r][c].tile_role = ROLE_BUILDING_CIVIC
                placed['police'] = (r0, c0)
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
    # A dead-end connector (only one neighbour road) = alley terminus
    alley_cells: set[tuple[int, int]] = set()
    for r, c, cell in grid.all_cells():
        if cell.is_road and cell.road_category == ROAD_CONNECTOR:
            tile_id = cell.layers.get(LAYER_ROAD) or ''
            if not tile_id.startswith('roundabout_'):
                bitmask = grid.road_bitmask(r, c)
                if bin(bitmask).count('1') == 1:
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
        if zone == ZONE_CBD:
            btype = _weighted_choice(rng, CBD_BLDG_WEIGHTS)
        elif zone == ZONE_MIDTOWN:
            btype = _weighted_choice(rng, MIDTOWN_BLDG_WEIGHTS)
        else:
            btype = _weighted_choice(rng, RESI_BLDG_WEIGHTS)
        # Assign directly to cells in this lot
        for r, c in lot_cells:
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

    yield GeneratorProgress(
        PHASE_BUILDINGS, 1.0,
        (
            f'Buildings phase complete — {len(lots)} lots typed, '
            f'{len(landmarks)} landmarks, {spawn_count} spawn points.'
        ),
    )
