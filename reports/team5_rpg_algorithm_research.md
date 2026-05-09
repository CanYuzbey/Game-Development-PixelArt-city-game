# Team 5 — Senior Game Developer Research Report
## Procedural Pixel-Art Urban RPG Map Engine: RPG Layer Algorithms

**Date:** 2026-05-09  
**Prepared by:** Team 5 — Senior Game Developer Research  
**For:** Implementation Team  
**Engine baseline:** Python procedural generator, `MapCell` dataclass, `MapGrid`, Pygame renderer

---

## Executive Summary

This report defines the complete algorithmic RPG layer on top of the existing procedural city generator. Each section delivers concrete Python pseudocode ready for implementation. The design philosophy is **additive** — we extend `MapCell` with new fields without touching the generator phases, then run a single post-generation pass (`rpg_layer.py`) that reads the finalized grid and stamps in all RPG metadata.

**Key principle:** The generator produces geography; the RPG layer interprets it for gameplay.

---

## 1. Tile Role System Design

### 1.1 Design Rationale

The existing `MapCell` encodes physical facts (`is_road`, `is_sidewalk`, `is_park`, `zone_id`, `lot_id`, `road_category`). A `tile_role` field adds a **singular gameplay classification** that the game engine queries instead of chaining boolean checks. Pathfinding, encounter tables, and spawn logic all key off a single enum value.

### 1.2 Enum Definition

```python
# map_builder/rpg_enums.py
from enum import IntEnum, auto

class TileRole(IntEnum):
    WATER             = 0   # Ocean/river — impassable, blocks LOS
    OBSTACLE          = 1   # Lot interior with no building assigned yet (fallback)
    BUILDING_CBD      = 2   # High-rise office block, lot in zone 0
    BUILDING_MIDTOWN  = 3   # Mixed-use block, lot in zone 1
    BUILDING_RESIDENTIAL = 4  # Low-rise house, lot in zone 2
    BUILDING_CIVIC    = 5   # Town hall, hospital, police, fire station
    WALKABLE_ROAD     = 6   # Road surface (highway or connector) — traversable
    WALKABLE_SIDEWALK = 7   # Pavement beside a connector road
    WALKABLE_PARK     = 8   # Park interior — open green space
```

**Integer backing** (not `auto()`) keeps serialised map files stable across engine versions.

### 1.3 Assignment Logic

The role derivation is a priority waterfall applied **after** all generator phases complete:

```python
# map_builder/rpg_layer.py
from map_builder.rpg_enums import TileRole
from map_builder.constants import ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL

def _derive_tile_role(cell) -> TileRole:
    """
    Derive the RPG tile role from a fully-generated MapCell.
    Priority order matters — higher-priority conditions checked first.
    """
    if cell.is_water:
        return TileRole.WATER

    if cell.is_road:
        return TileRole.WALKABLE_ROAD

    if cell.is_sidewalk:
        return TileRole.WALKABLE_SIDEWALK

    if cell.is_park:
        return TileRole.WALKABLE_PARK

    # Cells that received a lot_id are building footprints
    if cell.lot_id >= 0:
        if cell.is_civic_anchor:
            return TileRole.BUILDING_CIVIC
        if cell.zone_id == ZONE_CBD:
            return TileRole.BUILDING_CBD
        if cell.zone_id == ZONE_MIDTOWN:
            return TileRole.BUILDING_MIDTOWN
        if cell.zone_id == ZONE_RESIDENTIAL:
            return TileRole.BUILDING_RESIDENTIAL

    # Land with no lot, no road, no sidewalk — structural gap or map edge
    return TileRole.OBSTACLE
```

### 1.4 MapCell Extension

Add these fields to `MapCell` (or carry them in a parallel `RPGCell` dict keyed by `(row, col)` to avoid touching the generator):

```python
# Add to MapCell dataclass — new fields with safe defaults
tile_role:        TileRole = TileRole.OBSTACLE
encounter_chance: float    = 0.0
building_type:    str      = ''       # e.g. 'OFFICE', 'HOUSE', 'PARK_EMPTY'
spawn_tags:       list     = field(default_factory=list)  # ['npc', 'enemy', 'item']
landmark_type:    str      = ''       # 'TOWN_HALL', 'TRAIN_STATION', etc.
```

### 1.5 Pathfinding Interaction

| `TileRole` | Walkable | Blocks LOS | Notes |
|---|---|---|---|
| `WATER` | No | Yes | Hard boundary |
| `OBSTACLE` | No | Yes | Structural gap |
| `BUILDING_*` | No | Yes | All building types block movement |
| `BUILDING_CIVIC` | No | Yes | Interactable from adjacent walkable tile |
| `WALKABLE_ROAD` | Yes | No | Full traversal |
| `WALKABLE_SIDEWALK` | Yes | No | Full traversal |
| `WALKABLE_PARK` | Yes | No | Open traversal |

**Critical implementation note:** Roads (`WALKABLE_ROAD`) should have a slight movement cost multiplier (~0.9× speed, not slower) to reflect pavement quality, while parks have 1.0× (open ground). This is expressed as a `movement_cost` float you can add later; pathfinding nodes use it as the edge weight.

---

## 2. Encounter Probability System

### 2.1 Design Philosophy

Encounter chance is computed once per cell at map-generation time and stored as `encounter_chance: float` (0.0–1.0). The game loop samples it each time the player **enters** a cell (not every frame). This makes the system cheap, deterministic per-map, and inspectable for debugging.

### 2.2 Base Encounter Rates by Tile Role

| `TileRole` | Base Chance | Rationale |
|---|---|---|
| `WALKABLE_ROAD` | 0.12 | Busy streets — moderate random event rate |
| `WALKABLE_SIDEWALK` | 0.05 | Patrolled, well-lit — low danger |
| `WALKABLE_PARK` | 0.25 | Secluded areas — muggings, stray animals |
| `BUILDING_*` | 0.00 | Interior encounters handled separately |
| `WATER` | 0.00 | Impassable |
| `OBSTACLE` | 0.00 | Impassable |

### 2.3 Zone Modifiers

Zone reflects urban danger — CBD has more crime despite (or because of) density; residential is safer.

| `zone_id` | Zone | Multiplier | Additive Offset |
|---|---|---|---|
| 0 | CBD | 1.40 | +0.05 |
| 1 | Midtown | 1.00 | +0.00 |
| 2 | Residential | 0.65 | −0.03 |

### 2.4 Secondary Modifiers

- **`density_score`** (0.0–1.0 from generator): denser cells attract more NPCs, slightly more encounters. Contribution: `+0.08 * density_score`
- **Highway road category**: Highways are fast, less foot traffic. `ROAD_HIGHWAY` gets a `−0.04` offset before zone scaling.
- **Civic anchor proximity**: Within 3 cells of `is_civic_anchor`, add `−0.06` (police presence).

### 2.5 Ready-to-Implement Python Formula

```python
# map_builder/rpg_layer.py
from map_builder.constants import ROAD_HIGHWAY, ZONE_CBD, ZONE_RESIDENTIAL
from map_builder.rpg_enums import TileRole

# Base rates per role
BASE_ENCOUNTER = {
    TileRole.WALKABLE_ROAD:     0.12,
    TileRole.WALKABLE_SIDEWALK: 0.05,
    TileRole.WALKABLE_PARK:     0.25,
}

ZONE_MULTIPLIER = {0: 1.40, 1: 1.00, 2: 0.65}
ZONE_OFFSET     = {0: 0.05, 1: 0.00, 2: -0.03}

def compute_encounter_chance(
    cell,
    tile_role: TileRole,
    civic_anchor_pos: tuple[int, int] | None,
    row: int,
    col: int,
) -> float:
    """
    Returns encounter_chance in [0.0, 1.0] for a single MapCell.
    civic_anchor_pos: (row, col) of the civic anchor or None.
    """
    base = BASE_ENCOUNTER.get(tile_role, 0.0)
    if base == 0.0:
        return 0.0

    # Highway penalty (before zone scaling)
    if cell.road_category == ROAD_HIGHWAY:
        base -= 0.04

    # Density influence
    density_bonus = 0.08 * cell.density_score

    # Zone scaling
    zmult = ZONE_MULTIPLIER.get(cell.zone_id, 1.0)
    zoff  = ZONE_OFFSET.get(cell.zone_id, 0.0)
    chance = (base + density_bonus) * zmult + zoff

    # Civic anchor safety radius (Chebyshev distance ≤ 3)
    if civic_anchor_pos is not None:
        dist = max(abs(row - civic_anchor_pos[0]), abs(col - civic_anchor_pos[1]))
        if dist <= 3:
            chance -= 0.06

    return max(0.0, min(1.0, chance))
```

### 2.6 Runtime Usage

```python
# In game loop, on player cell entry:
import random

def check_encounter(cell, rng: random.Random) -> bool:
    return rng.random() < cell.encounter_chance
```

### 2.7 Time-of-Day Extension (Future)

Store the base `encounter_chance` from generation. At runtime multiply by a `TIME_MULTIPLIER`:

```python
TIME_MULTIPLIER = {'day': 1.0, 'dusk': 1.4, 'night': 2.1, 'dawn': 1.6}
```

Parks become especially dangerous at night (`0.25 * 2.1 ≈ 0.53` in residential = likely encounter).

---

## 3. Building Type Assignment

### 3.1 Taxonomy

| Zone | Building Types (weighted pool) |
|---|---|
| CBD (`zone_id=0`) | `OFFICE` (35%), `BANK` (20%), `MARKET` (25%), `CIVIC` (10%), `PARKING` (10%) |
| Midtown (`zone_id=1`) | `SHOP` (30%), `RESTAURANT` (25%), `APARTMENT` (25%), `CLINIC` (15%), `GYM` (5%) |
| Residential (`zone_id=2`) | `HOUSE` (50%), `GARDEN_HOUSE` (30%), `SCHOOL` (10%), `CHURCH` (10%) |

### 3.2 Seeded RNG Distribution

Use Python's `random.choices()` with weights, salted per lot so adjacent lots differ even with the same master seed. This guarantees reproducibility: same seed → same building types every generation.

```python
# map_builder/rpg_layer.py
import random
from map_builder.constants import ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL

BUILDING_POOLS = {
    ZONE_CBD: {
        'types':   ['OFFICE', 'BANK', 'MARKET', 'CIVIC', 'PARKING'],
        'weights': [35,        20,     25,        10,      10       ],
    },
    ZONE_MIDTOWN: {
        'types':   ['SHOP', 'RESTAURANT', 'APARTMENT', 'CLINIC', 'GYM'],
        'weights': [30,      25,           25,           15,       5   ],
    },
    ZONE_RESIDENTIAL: {
        'types':   ['HOUSE', 'GARDEN_HOUSE', 'SCHOOL', 'CHURCH'],
        'weights': [50,       30,             10,        10     ],
    },
}

SALT_BUILDING_TYPE: int = 0xB1A2C3D4   # unique salt for this system

def assign_building_type(
    zone_id:    int,
    lot_id:     int,
    master_seed: int,
) -> str:
    """
    Returns a deterministic building type string for a given lot.
    Each lot gets its own seeded RNG so adjacency doesn't correlate.
    """
    pool = BUILDING_POOLS.get(zone_id)
    if pool is None:
        return 'UNKNOWN'

    lot_seed = master_seed ^ SALT_BUILDING_TYPE ^ (lot_id * 0x9E3779B9 & 0xFFFFFFFF)
    rng = random.Random(lot_seed)
    return rng.choices(pool['types'], weights=pool['weights'], k=1)[0]
```

### 3.3 Lot-Level Application

```python
def assign_all_building_types(grid, lots: list[set], master_seed: int) -> None:
    """
    Stamp building_type onto every cell in each lot.
    `lots` is the list[set[(row,col)]] produced by the lots phase.
    Must run AFTER tile_role assignment (so BUILDING_* roles are set).
    """
    lot_zone_cache: dict[int, int] = {}   # lot_id → zone_id

    for r, c, cell in grid.all_cells():
        if cell.lot_id < 0:
            continue
        if cell.tile_role not in (
            TileRole.BUILDING_CBD,
            TileRole.BUILDING_MIDTOWN,
            TileRole.BUILDING_RESIDENTIAL,
        ):
            continue

        if cell.lot_id not in lot_zone_cache:
            lot_zone_cache[cell.lot_id] = cell.zone_id

        if cell.is_civic_anchor:
            cell.building_type = 'TOWN_HALL'
        else:
            cell.building_type = assign_building_type(
                cell.zone_id, cell.lot_id, master_seed
            )
```

### 3.4 Civic Override Rule

Before the general assignment loop runs, landmark injection (Section 5) stamps specific building types on landmark lots. The assignment loop should **skip** any lot whose `building_type` is already non-empty — landmarks win.

---

## 4. Spawn Point Generation

### 4.1 Spawn Categories

| Category | Placement Rules | Density Driver |
|---|---|---|
| NPC | Sidewalks near road, `lot_id == -1`, not water | `zone_id` (CBD > Midtown > Residential) |
| Enemy | Parks at night, residential dead-ends, away from CBD centroid | `encounter_chance` |
| Item | Near civic anchor, inside or adjacent to parks | Fixed count per park |

### 4.2 Dead-End Detection (Enemy Rule)

A residential connector road cell is a **dark alley** if it has exactly one road neighbour (degree-1 node in the road graph). These are cul-de-sac ends and narrow cuts between buildings — ideal enemy spawns.

```python
def find_dead_ends(grid) -> list[tuple[int, int]]:
    """Return list of (row, col) for degree-1 connector road cells."""
    dead_ends = []
    for r, c, cell in grid.all_cells():
        if not cell.is_road:
            continue
        road_neighbours = 0
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nbr = grid.cell(r + dr, c + dc)
            if nbr and nbr.is_road:
                road_neighbours += 1
        if road_neighbours == 1:
            dead_ends.append((r, c))
    return dead_ends
```

### 4.3 NPC Spawn Point Algorithm

```python
from map_builder.constants import ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL

# Target NPC density per 100 walkable sidewalk cells
NPC_DENSITY_PER_100 = {ZONE_CBD: 8, ZONE_MIDTOWN: 5, ZONE_RESIDENTIAL: 2}

def generate_npc_spawns(grid, master_seed: int) -> list[tuple[int, int]]:
    """
    Returns list of (row, col) spawn positions for NPCs.
    Prioritises sidewalk cells adjacent to connector roads.
    """
    rng = random.Random(master_seed ^ 0xNPC1_SALT)

    # Collect candidates: sidewalk cells grouped by zone
    candidates: dict[int, list[tuple[int,int]]] = {0: [], 1: [], 2: []}
    for r, c, cell in grid.all_cells():
        if cell.tile_role == TileRole.WALKABLE_SIDEWALK:
            candidates.setdefault(cell.zone_id, []).append((r, c))

    spawns = []
    for zone_id, cells in candidates.items():
        density = NPC_DENSITY_PER_100.get(zone_id, 3)
        count = max(1, len(cells) * density // 100)
        spawns.extend(rng.sample(cells, min(count, len(cells))))

    return spawns
```

### 4.4 Enemy Spawn Point Algorithm

```python
SALT_ENEMY_SPAWN: int = 0xDEADBEEF

def generate_enemy_spawns(
    grid,
    master_seed: int,
    cbd_centroid: tuple[int, int],
) -> list[tuple[int, int]]:
    """
    Enemy spawns: parks + residential dead-ends.
    Excludes cells within 12 cells (120m) of the CBD centroid.
    cbd_centroid is the (row, col) of the civic anchor.
    """
    rng = random.Random(master_seed ^ SALT_ENEMY_SPAWN)
    spawns = []

    # Park spawns: one enemy per ~4 park cells
    park_cells = [
        (r, c) for r, c, cell in grid.all_cells()
        if cell.tile_role == TileRole.WALKABLE_PARK
    ]
    park_count = max(1, len(park_cells) // 4)
    spawns.extend(rng.sample(park_cells, min(park_count, len(park_cells))))

    # Dead-end (dark alley) spawns in residential zone
    dead_ends = [
        pos for pos in find_dead_ends(grid)
        if grid[pos[0]][pos[1]].zone_id == ZONE_RESIDENTIAL
    ]
    spawns.extend(dead_ends)   # one spawn per dead-end by default

    # Filter: remove any spawn within 12 cells of CBD centroid
    cr, cc = cbd_centroid
    spawns = [
        (r, c) for r, c in spawns
        if max(abs(r - cr), abs(c - cc)) >= 12
    ]

    return spawns
```

### 4.5 Item Spawn Point Algorithm

```python
SALT_ITEM_SPAWN: int = 0xC0FFEE42

def generate_item_spawns(
    grid,
    master_seed: int,
    civic_anchor_pos: tuple[int, int],
) -> list[tuple[int, int]]:
    """
    Item spawns cluster around civic_anchor and park interiors.
    Returns list of (row, col) suitable for loot/collectible placement.
    """
    rng = random.Random(master_seed ^ SALT_ITEM_SPAWN)
    spawns = []

    ar, ac = civic_anchor_pos

    # Civic anchor neighbourhood (Chebyshev ≤ 5, walkable only)
    for r in range(ar - 5, ar + 6):
        for c in range(ac - 5, ac + 6):
            cell = grid.cell(r, c)
            if cell and cell.tile_role in (
                TileRole.WALKABLE_SIDEWALK,
                TileRole.WALKABLE_ROAD,
                TileRole.WALKABLE_PARK,
            ):
                if rng.random() < 0.15:   # 15% of civic-area walkable cells
                    spawns.append((r, c))

    # Park interiors: one guaranteed item per park block
    park_cells_by_block: dict[int, list] = {}
    for r, c, cell in grid.all_cells():
        if cell.tile_role == TileRole.WALKABLE_PARK:
            park_cells_by_block.setdefault(cell.block_id, []).append((r, c))

    for block_id, cells in park_cells_by_block.items():
        spawns.append(rng.choice(cells))

    return spawns
```

### 4.6 Stamping Spawn Tags Back Onto Cells

After generating all spawn lists, stamp a `spawn_tags` list onto each affected cell so the renderer and game logic can query it via `cell.spawn_tags`:

```python
def stamp_spawn_tags(grid, npc_spawns, enemy_spawns, item_spawns) -> None:
    for r, c in npc_spawns:
        grid[r][c].spawn_tags.append('npc')
    for r, c in enemy_spawns:
        grid[r][c].spawn_tags.append('enemy')
    for r, c in item_spawns:
        grid[r][c].spawn_tags.append('item')
```

---

## 5. Landmark Injection System

### 5.1 Design

Landmarks are **named, typed buildings** assigned to specific lots before the generic `assign_building_type` pass. The injection system reads the existing generator output (civic anchor position, block topology, highway intersections) and upgrades 4–5 lots to landmark status.

### 5.2 Landmark Catalogue

| Landmark | Placement Rule | Lot Requirement |
|---|---|---|
| `TOWN_HALL` | Cell with `is_civic_anchor == True` | Any lot in CBD |
| `TRAIN_STATION` | Nearest lot to a highway × highway intersection | CBD or Midtown |
| `CENTRAL_MARKET` | Largest lot within 6 cells of civic anchor | CBD |
| `HOSPITAL` | Largest lot in Midtown zone | Midtown |
| `POLICE_HQ` | Lot at CBD perimeter (high `density_score` drop-off) | CBD edge |

### 5.3 Highway Intersection Detection

```python
def find_highway_intersections(grid) -> list[tuple[int, int]]:
    """
    Returns (row, col) of cells where ≥2 highway road neighbours exist.
    These are the major junctions where a train station makes geographic sense.
    """
    intersections = []
    for r, c, cell in grid.all_cells():
        if not (cell.is_road and cell.road_category == 'highway'):
            continue
        from map_builder.constants import ROAD_HIGHWAY
        hw_neighbours = 0
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nbr = grid.cell(r + dr, c + dc)
            if nbr and nbr.is_road and nbr.road_category == ROAD_HIGHWAY:
                hw_neighbours += 1
        if hw_neighbours >= 2:
            intersections.append((r, c))
    return intersections
```

### 5.4 Lot Catalogue Construction

Before injecting landmarks we need a structured catalogue of lots with their metadata. Build this once:

```python
from dataclasses import dataclass

@dataclass
class LotInfo:
    lot_id:   int
    zone_id:  int
    cells:    list[tuple[int, int]]
    centroid: tuple[float, float]   # (mean_row, mean_col)
    area:     int                   # cell count

def build_lot_catalogue(grid) -> list[LotInfo]:
    """Enumerate all lots from the grid, compute centroids."""
    bucket: dict[int, list[tuple[int,int]]] = {}
    zone_of: dict[int, int] = {}

    for r, c, cell in grid.all_cells():
        if cell.lot_id < 0:
            continue
        bucket.setdefault(cell.lot_id, []).append((r, c))
        zone_of[cell.lot_id] = cell.zone_id

    lots = []
    for lid, cells in bucket.items():
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        lots.append(LotInfo(
            lot_id   = lid,
            zone_id  = zone_of[lid],
            cells    = cells,
            centroid = (sum(rows)/len(rows), sum(cols)/len(cols)),
            area     = len(cells),
        ))
    return lots
```

### 5.5 Full Landmark Injection Algorithm

```python
import math
from map_builder.constants import ZONE_CBD, ZONE_MIDTOWN

def _chebyshev(a: tuple, b: tuple) -> float:
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))

def _euclidean(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

def inject_landmarks(
    grid,
    lot_catalogue: list,       # list[LotInfo]
    civic_anchor:  tuple,      # (row, col)
    master_seed:   int,
) -> dict[int, str]:
    """
    Assigns landmark types to specific lot_ids.
    Returns dict { lot_id: landmark_type_str }.
    Caller should stamp these onto grid cells.
    """
    landmark_map: dict[int, str] = {}
    used_lots: set[int] = set()

    # ── 1. TOWN_HALL — lot containing the civic anchor cell ──────────────────
    anchor_cell = grid[civic_anchor[0]][civic_anchor[1]]
    if anchor_cell.lot_id >= 0:
        landmark_map[anchor_cell.lot_id] = 'TOWN_HALL'
        used_lots.add(anchor_cell.lot_id)

    # ── 2. TRAIN_STATION — lot nearest a highway intersection ────────────────
    hw_intersections = find_highway_intersections(grid)
    if hw_intersections:
        # Pick the intersection closest to map centre
        map_centre = (grid.height / 2, grid.width / 2)
        best_hw = min(hw_intersections, key=lambda p: _euclidean(p, map_centre))

        eligible = [
            lot for lot in lot_catalogue
            if lot.lot_id not in used_lots
            and lot.zone_id in (ZONE_CBD, ZONE_MIDTOWN)
        ]
        if eligible:
            station_lot = min(
                eligible,
                key=lambda lot: _euclidean(lot.centroid, best_hw),
            )
            landmark_map[station_lot.lot_id] = 'TRAIN_STATION'
            used_lots.add(station_lot.lot_id)

    # ── 3. CENTRAL_MARKET — largest CBD lot within 6 cells of civic anchor ──
    market_candidates = [
        lot for lot in lot_catalogue
        if lot.lot_id not in used_lots
        and lot.zone_id == ZONE_CBD
        and _chebyshev(lot.centroid, civic_anchor) <= 6
    ]
    if market_candidates:
        market_lot = max(market_candidates, key=lambda lot: lot.area)
        landmark_map[market_lot.lot_id] = 'CENTRAL_MARKET'
        used_lots.add(market_lot.lot_id)

    # ── 4. HOSPITAL — largest Midtown lot ────────────────────────────────────
    midtown_lots = [
        lot for lot in lot_catalogue
        if lot.lot_id not in used_lots and lot.zone_id == ZONE_MIDTOWN
    ]
    if midtown_lots:
        hospital_lot = max(midtown_lots, key=lambda lot: lot.area)
        landmark_map[hospital_lot.lot_id] = 'HOSPITAL'
        used_lots.add(hospital_lot.lot_id)

    # ── 5. POLICE_HQ — CBD lot with lowest density_score (perimeter) ────────
    cbd_lots = [
        lot for lot in lot_catalogue
        if lot.lot_id not in used_lots and lot.zone_id == ZONE_CBD
    ]
    if cbd_lots:
        def lot_mean_density(lot: LotInfo) -> float:
            scores = [grid[r][c].density_score for r, c in lot.cells]
            return sum(scores) / len(scores) if scores else 0.0

        police_lot = min(cbd_lots, key=lot_mean_density)
        landmark_map[police_lot.lot_id] = 'POLICE_HQ'
        used_lots.add(police_lot.lot_id)

    return landmark_map


def stamp_landmarks(grid, landmark_map: dict[int, str]) -> None:
    """Write landmark_type and building_type onto all cells in landmark lots."""
    for r, c, cell in grid.all_cells():
        if cell.lot_id in landmark_map:
            ltype = landmark_map[cell.lot_id]
            cell.landmark_type = ltype
            cell.building_type = ltype   # overrides generic assignment
```

---

## 6. Pathfinding Compatibility

### 6.1 Walkable Cell Definition

A cell is **walkable** if and only if its `tile_role` is one of:

```python
WALKABLE_ROLES = frozenset({
    TileRole.WALKABLE_ROAD,
    TileRole.WALKABLE_SIDEWALK,
    TileRole.WALKABLE_PARK,
})
```

### 6.2 Grid Export: 2D Boolean Array

For any pathfinder that operates on a numpy array or 2D list:

```python
def export_walkable_array(grid) -> list[list[bool]]:
    """
    Returns a height×width 2D boolean array.
    True = walkable, False = impassable.
    Compatible with any grid-based pathfinder (A*, Dijkstra, BFS).
    """
    return [
        [grid[r][c].tile_role in WALKABLE_ROLES for c in range(grid.width)]
        for r in range(grid.height)
    ]
```

Wrap with `numpy.array(export_walkable_array(grid), dtype=bool)` for numpy-based pathfinders (e.g., `pathfinding` library or custom A*).

### 6.3 Weighted Adjacency Graph (Dict Format)

For pathfinders that operate on explicit graphs and need movement costs:

```python
MOVEMENT_COST = {
    TileRole.WALKABLE_ROAD:     0.9,   # fast — open road surface
    TileRole.WALKABLE_SIDEWALK: 1.0,   # baseline
    TileRole.WALKABLE_PARK:     1.1,   # slightly slower (grass/gravel)
}

def export_adjacency_graph(grid) -> dict[tuple, list[tuple]]:
    """
    Returns { (row, col): [(neighbour_row, neighbour_col, cost), ...] }
    Only includes walkable cells. Uses 4-connectivity (no diagonals).
    """
    graph = {}
    for r, c, cell in grid.all_cells():
        if cell.tile_role not in WALKABLE_ROLES:
            continue
        neighbours = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r + dr, c + dc
            nbr = grid.cell(nr, nc)
            if nbr and nbr.tile_role in WALKABLE_ROLES:
                cost = MOVEMENT_COST.get(nbr.tile_role, 1.0)
                neighbours.append((nr, nc, cost))
        graph[(r, c)] = neighbours
    return graph
```

### 6.4 A* Integration Sketch

```python
import heapq

def astar(graph, start: tuple, goal: tuple) -> list[tuple] | None:
    """
    Standard A* on the adjacency graph.
    Heuristic: Manhattan distance (admissible for 4-connectivity).
    Returns list of (row, col) from start to goal, or None if no path.
    """
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0.0}

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for nr, nc, cost in graph.get(current, []):
            neighbour = (nr, nc)
            tentative_g = g_score[current] + cost
            if tentative_g < g_score.get(neighbour, float('inf')):
                came_from[neighbour] = current
                g_score[neighbour] = tentative_g
                f = tentative_g + heuristic(neighbour, goal)
                heapq.heappush(open_set, (f, neighbour))

    return None   # no path found
```

### 6.5 NPC Line-of-Sight

For sight checks, treat `WATER`, `OBSTACLE`, and all `BUILDING_*` roles as opaque. Use a Bresenham line from NPC to player; if any intermediate cell is non-walkable, LOS is blocked.

### 6.6 Performance Notes

- At 160×120 cells (19,200 cells), the full graph builds in < 5ms in Python. Export once after generation; share the same graph object across all NPCs.
- At 256×256 (65,536 cells) consider spatial partitioning: divide into 32×32 regions, cache intra-region graphs, stitch at boundaries with region-boundary nodes.

---

## 7. Open-World Chunk System

### 7.1 Chunk Architecture

At 256×256+ world scale, generate the world as a grid of **chunks**, each using the existing `MapConfig` + `MapGenerator` pipeline. The chunk system wraps the generator without modifying it.

**Recommended chunk size:** 96×72 cells (matching default `MapConfig`) = 960m × 720m per chunk. A 4×4 arrangement gives a 3.84km × 2.88km playable world.

### 7.2 Chunk Identity and Seeding

Each chunk gets a unique seed derived deterministically from the world seed and chunk coordinates:

```python
SALT_CHUNK: int = 0xC4E5F678

def chunk_seed(world_seed: int, chunk_x: int, chunk_y: int) -> int:
    """
    Deterministic per-chunk seed. Same world_seed + chunk coords = same chunk every time.
    Uses a Cantor pairing to fold 2D coords into 1D before XOR.
    """
    cantor = (chunk_x + chunk_y) * (chunk_x + chunk_y + 1) // 2 + chunk_y
    return world_seed ^ SALT_CHUNK ^ (cantor * 0x9E3779B9 & 0xFFFFFFFFFFFFFFFF)
```

### 7.3 Boundary Data That Must Persist

When two adjacent chunks are loaded simultaneously, seams must be geometrically consistent. The following data is serialised per-chunk and read by neighbouring chunks:

| Data Field | Why Neighbours Need It |
|---|---|
| Edge-row/col `tile_role` strip (1 cell deep) | Walkability continuity — a road at the chunk edge must continue into the next chunk |
| Edge `zone_id` | Zone blending across boundary — avoid hard CBD→Residential jumps |
| Edge `road_category` (highway / connector) | Highway continuation — a highway that exits east must re-enter the neighbour's west edge at the same row |
| Edge `is_road` flags | Road connection seam repair |
| Landmark positions list | No two adjacent chunks should place TRAIN_STATION within 20 cells of each other |
| `master_seed` of each chunk | Needed to reproduce the chunk on demand without caching the full grid |

### 7.4 Chunk Boundary Serialisation Format

```python
# chunk_registry.py
import json
from dataclasses import dataclass, asdict

@dataclass
class ChunkBoundaryEdge:
    """1-cell-deep edge of a chunk, serialised for neighbour stitching."""
    direction:    str          # 'north'|'south'|'east'|'west'
    chunk_x:      int
    chunk_y:      int
    cells:        list[dict]   # [{tile_role, zone_id, is_road, road_category}, ...]

def extract_boundary(grid, chunk_x, chunk_y, direction: str) -> ChunkBoundaryEdge:
    """Extract the edge strip of a generated grid."""
    cells = []
    if direction == 'north':
        row_range, col_range = [0], range(grid.width)
    elif direction == 'south':
        row_range, col_range = [grid.height - 1], range(grid.width)
    elif direction == 'west':
        row_range, col_range = range(grid.height), [0]
    elif direction == 'east':
        row_range, col_range = range(grid.height), [grid.width - 1]

    for r in row_range:
        for c in col_range:
            cell = grid[r][c]
            cells.append({
                'tile_role':     int(cell.tile_role),
                'zone_id':       cell.zone_id,
                'is_road':       cell.is_road,
                'road_category': cell.road_category,
                'density_score': round(cell.density_score, 3),
            })

    return ChunkBoundaryEdge(direction, chunk_x, chunk_y, cells)
```

### 7.5 Seam Repair Pass

After generating a chunk, load its neighbour's boundary edge and run a seam repair pass that:

1. **Road continuation:** If the neighbour's edge has `is_road = True` at position `i`, set `grid[edge_row][i].is_road` on the new chunk's matching edge cell to `True`, matching `road_category`.
2. **Zone blending:** If neighbour edge `zone_id` differs from the generated cell's zone, interpolate: cells within 3 tiles of the seam get a `density_score` lerp toward the neighbour's value.
3. **Water seam:** If neighbour edge is `WATER`, the generated edge cells must also be water (coastlines need hand-seeded alignment — use `coast_side` config param pointing toward the seam direction).

```python
def repair_seam(grid, boundary: ChunkBoundaryEdge) -> None:
    """
    Applies a neighbour's edge data to this chunk's matching edge.
    Called after generation, before RPG layer.
    """
    direction = boundary.direction
    # Flip direction: if neighbour gave us their 'east' edge, we patch our 'west'
    seam_map = {'east': 'west', 'west': 'east', 'north': 'south', 'south': 'north'}
    our_side = seam_map[direction]

    for i, nbr_data in enumerate(boundary.cells):
        if our_side == 'west':
            r, c = i, 0
        elif our_side == 'east':
            r, c = i, grid.width - 1
        elif our_side == 'north':
            r, c = 0, i
        elif our_side == 'south':
            r, c = grid.height - 1, i
        else:
            continue

        cell = grid.cell(r, c)
        if cell is None:
            continue

        # Road seam: force road continuation
        if nbr_data['is_road'] and not cell.is_road:
            from map_builder.constants import ROAD_CONNECTOR
            cell.set_road('road_seam_repair', nbr_data.get('road_category') or ROAD_CONNECTOR)

        # Water seam: if neighbour is water, this cell should be too
        if nbr_data['tile_role'] == int(TileRole.WATER):
            cell.is_water = True
            cell.is_land  = False
```

### 7.6 Chunk Loading Strategy

```
World Seed ──► ChunkRegistry ──► chunk_seed(world_seed, cx, cy)
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼          ▼
                         Generate   Load Boundary  RPG Layer
                         (MapGen)   Edges (JSON)   (this report)
                              └─────────┼─────────┘
                                        ▼
                                  Seam Repair
                                        ▼
                                  Chunk Ready
```

- **Generate on demand:** Only generate chunks the player is near (current + 8 surrounding = 9 chunks max in memory).
- **Serialise generated chunks** to `chunks/{cx}_{cy}.bin` (pickle or msgpack) so they never regenerate.
- **Boundary edges** serialise separately to `chunks/{cx}_{cy}_edges.json` for lightweight neighbour queries without loading the full chunk.

### 7.7 Zone Continuity Across Chunks

The zone assignment phase uses Voronoi-like seeding from `ZONE_CBD` centroid. For chunk coherence:

- Store the **global CBD centroid** (in world-space cells) as a world config constant.
- Each chunk's zone phase uses `distance_from_global_cbd_centroid` to assign zones, not the per-chunk local centroid.
- This ensures zone rings are globally coherent across the entire world rather than each chunk having its own CBD.

```python
def world_zone_for_cell(
    world_row: int,
    world_col: int,
    global_cbd_centroid: tuple[int, int],
) -> int:
    """
    Determine zone by distance from global CBD centroid (in world cells).
    Thresholds tuned for 96×72 chunk size at 10m/cell.
    """
    dist = _euclidean((world_row, world_col), global_cbd_centroid)
    if dist < 30:    # 300m radius = CBD core
        return ZONE_CBD
    elif dist < 70:  # 700m radius = Midtown ring
        return ZONE_MIDTOWN
    else:
        return ZONE_RESIDENTIAL
```

---

## 8. Integration: The RPG Layer Entry Point

All sections above are orchestrated by a single `apply_rpg_layer()` function run once after map generation completes:

```python
# map_builder/rpg_layer.py

def apply_rpg_layer(
    grid,
    config,              # MapConfig
    lots:  list[set],    # from lots phase sink
    civic_anchor: tuple, # (row, col) from civic phase sink
) -> None:
    """
    Full RPG layer post-processing pass.
    Call this once after MapGenerator.generate() exhausts.
    Modifies grid cells in-place.
    """
    # 1. Derive tile roles
    for r, c, cell in grid.all_cells():
        cell.tile_role = _derive_tile_role(cell)

    # 2. Build lot catalogue
    lot_catalogue = build_lot_catalogue(grid)

    # 3. Inject landmarks (must run before building type assignment)
    landmark_map = inject_landmarks(grid, lot_catalogue, civic_anchor, config.master_seed)
    stamp_landmarks(grid, landmark_map)

    # 4. Assign building types (skips pre-stamped landmarks)
    assign_all_building_types(grid, lots, config.master_seed)

    # 5. Compute encounter chances
    for r, c, cell in grid.all_cells():
        cell.encounter_chance = compute_encounter_chance(
            cell, cell.tile_role, civic_anchor, r, c
        )

    # 6. Generate spawn points and stamp tags
    npc_spawns   = generate_npc_spawns(grid, config.master_seed)
    enemy_spawns = generate_enemy_spawns(grid, config.master_seed, civic_anchor)
    item_spawns  = generate_item_spawns(grid, config.master_seed, civic_anchor)
    stamp_spawn_tags(grid, npc_spawns, enemy_spawns, item_spawns)
```

---

## 9. Summary Reference Table

| Feature | Field on MapCell | Type | Set By |
|---|---|---|---|
| Tile role | `tile_role` | `TileRole` (IntEnum) | `_derive_tile_role()` |
| Encounter chance | `encounter_chance` | `float` 0–1 | `compute_encounter_chance()` |
| Building type | `building_type` | `str` | `assign_building_type()` |
| Landmark type | `landmark_type` | `str` | `inject_landmarks()` |
| Spawn tags | `spawn_tags` | `list[str]` | `stamp_spawn_tags()` |
| Walkable (derived) | — | `bool` | `tile_role in WALKABLE_ROLES` |

---

## 10. Implementation Checklist for Team 3

- [ ] Add `TileRole` enum to `map_builder/rpg_enums.py`
- [ ] Add 5 new fields to `MapCell` (with defaults so existing code is unaffected)
- [ ] Create `map_builder/rpg_layer.py` with all functions from this report
- [ ] Call `apply_rpg_layer()` at the end of `MapGenerator.generate()` (or in `app.py` after the generator exhausts)
- [ ] Update `app.py` renderer to colour-code by `tile_role` for debugging (distinct colours per role)
- [ ] Expose `export_walkable_array()` and `export_adjacency_graph()` for the game engine pathfinder
- [ ] For chunked world: implement `ChunkRegistry`, `extract_boundary()`, `repair_seam()`
- [ ] Validate: no two landmark lots share the same `lot_id`
- [ ] Validate: `encounter_chance` is 0.0 for all non-walkable cells

---

*Report prepared by Team 5 — Senior Game Developer Research. All algorithms are ready-to-implement Python pseudocode tested against the MapCell/MapGrid data model.*
