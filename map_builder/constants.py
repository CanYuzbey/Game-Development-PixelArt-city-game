"""
map_builder/constants.py
────────────────────────
All shared constants for the map builder engine.
No imports from other map_builder modules — safe to import anywhere.
"""
from typing import Final

# ── Connection types (per tile edge) ─────────────────────────────────────────
CONN_OPEN:     Final[int] = 0   # Empty air / future building lot
CONN_ROAD:     Final[int] = 1   # Road surface connects here
CONN_WATER:    Final[int] = 3   # Water (impassable, never receives road)

# ── Direction indices into 4-element (N, E, S, W) tuples ─────────────────────
N: Final[int] = 0
E: Final[int] = 1
S: Final[int] = 2
W: Final[int] = 3

DIRECTION_OFFSETS: Final[dict] = {
    N: (-1,  0),   # (row_delta, col_delta)
    E: ( 0,  1),
    S: ( 1,  0),
    W: ( 0, -1),
}
OPPOSITE_DIR: Final[dict] = {N: S, S: N, E: W, W: E}
ALL_DIRS:     Final[tuple] = (N, E, S, W)

# ── Bitmask weights  (N=8  E=4  S=2  W=1) ────────────────────────────────────
# Road tile selection: build a 4-bit integer from which neighbours are roads.
DIR_BIT: Final[dict] = {N: 8, E: 4, S: 2, W: 1}

# ── Map cell layers ───────────────────────────────────────────────────────────
LAYER_GROUND:   Final[int] = 0  # Water or bare land
LAYER_ROAD:     Final[int] = 1  # Road surface tile
LAYER_SIDEWALK: Final[int] = 2  # Sidewalk tile (on land cells adjacent to road)
LAYER_DECOR:    Final[int] = 3  # Overlay: cracks, puddles, markings

# ── Road categories ───────────────────────────────────────────────────────────
ROAD_HIGHWAY:   Final[str] = 'highway'    # Phase 2 — main arteries, no sidewalk
ROAD_CONNECTOR: Final[str] = 'connector'  # Phase 3 — branching streets, gets sidewalk

# ── Generation phase names (for progress reporting) ───────────────────────────
PHASE_COASTLINE:  Final[str] = 'coastline'
PHASE_HIGHWAY:    Final[str] = 'highway'
PHASE_CONNECTOR:  Final[str] = 'connector'
PHASE_SIDEWALK:   Final[str] = 'sidewalk'
PHASE_DECORATION: Final[str] = 'decoration'
PHASE_COMPLETE:   Final[str] = 'complete'

# ── Per-phase PRNG salts (XOR with master_seed) ───────────────────────────────
SALT_COAST:     Final[int] = 0xAB1234
SALT_HIGHWAY:   Final[int] = 0xCD5678
SALT_CONNECTOR: Final[int] = 0xEF9ABC
SALT_SIDEWALK:  Final[int] = 0x123DEF
SALT_DECOR:     Final[int] = 0x456789

# ── Coast sides ───────────────────────────────────────────────────────────────
COAST_NONE:   Final[str] = 'none'
COAST_NORTH:  Final[str] = 'north'
COAST_SOUTH:  Final[str] = 'south'
COAST_EAST:   Final[str] = 'east'
COAST_WEST:   Final[str] = 'west'
COAST_RANDOM: Final[str] = 'random'

# ── Sprite sheet identifiers ──────────────────────────────────────────────────
SHEET_ROADS:     Final[str] = 'roads'
SHEET_SIDEWALKS: Final[str] = 'sidewalks'

# ── Tile IDs — Roads ──────────────────────────────────────────────────────────
# Named by their bitmask value for clarity.
# Bitmask: N=8, E=4, S=2, W=1  →  range 0-15
# Each highway/connector variant shares the same bitmask key; category
# selects which sprite row to draw from.

TILE_ROAD_ISOLATED:    Final[str] = 'road_0000'   # 0  — orphan, fallback only
TILE_ROAD_END_W:       Final[str] = 'road_0001'   # 1
TILE_ROAD_END_S:       Final[str] = 'road_0010'   # 2
TILE_ROAD_CORNER_SW:   Final[str] = 'road_0011'   # 3
TILE_ROAD_END_E:       Final[str] = 'road_0100'   # 4
TILE_ROAD_STRAIGHT_EW: Final[str] = 'road_0101'   # 5
TILE_ROAD_CORNER_SE:   Final[str] = 'road_0110'   # 6
TILE_ROAD_T_ESW:       Final[str] = 'road_0111'   # 7  — open N
TILE_ROAD_END_N:       Final[str] = 'road_1000'   # 8
TILE_ROAD_CORNER_NW:   Final[str] = 'road_1001'   # 9
TILE_ROAD_STRAIGHT_NS: Final[str] = 'road_1010'   # 10
TILE_ROAD_T_NSW:       Final[str] = 'road_1011'   # 11 — open E
TILE_ROAD_CORNER_NE:   Final[str] = 'road_1100'   # 12
TILE_ROAD_T_NEW:       Final[str] = 'road_1101'   # 13 — open S
TILE_ROAD_T_NES:       Final[str] = 'road_1110'   # 14 — open W
TILE_ROAD_X:           Final[str] = 'road_1111'   # 15 — 4-way

# Bitmask → road tile ID (shared by highway and connector, sprite differs)
ROAD_BITMASK_TO_TILE: Final[dict] = {
    0:  TILE_ROAD_ISOLATED,
    1:  TILE_ROAD_END_W,
    2:  TILE_ROAD_END_S,
    3:  TILE_ROAD_CORNER_SW,
    4:  TILE_ROAD_END_E,
    5:  TILE_ROAD_STRAIGHT_EW,
    6:  TILE_ROAD_CORNER_SE,
    7:  TILE_ROAD_T_ESW,
    8:  TILE_ROAD_END_N,
    9:  TILE_ROAD_CORNER_NW,
    10: TILE_ROAD_STRAIGHT_NS,
    11: TILE_ROAD_T_NSW,
    12: TILE_ROAD_CORNER_NE,
    13: TILE_ROAD_T_NEW,
    14: TILE_ROAD_T_NES,
    15: TILE_ROAD_X,
}

# ── Tile IDs — Sidewalks ──────────────────────────────────────────────────────
# Sidewalk tiles are placed on land cells adjacent to connector roads.
# The bitmask encodes which of the cell's sides face a road.

TILE_SW_SURFACE:       Final[str] = 'sw_surface'     # Interior sidewalk, no curb edge
TILE_SW_EDGE_N:        Final[str] = 'sw_edge_n'      # Road is to the North  → curb on N face
TILE_SW_EDGE_E:        Final[str] = 'sw_edge_e'
TILE_SW_EDGE_S:        Final[str] = 'sw_edge_s'
TILE_SW_EDGE_W:        Final[str] = 'sw_edge_w'
TILE_SW_CORNER_NE:     Final[str] = 'sw_corner_ne'   # Road on N and E
TILE_SW_CORNER_NW:     Final[str] = 'sw_corner_nw'
TILE_SW_CORNER_SE:     Final[str] = 'sw_corner_se'
TILE_SW_CORNER_SW:     Final[str] = 'sw_corner_sw'
TILE_SW_END_N:         Final[str] = 'sw_end_n'       # Dead-end terminus, road on N
TILE_SW_END_E:         Final[str] = 'sw_end_e'
TILE_SW_END_S:         Final[str] = 'sw_end_s'
TILE_SW_END_W:         Final[str] = 'sw_end_w'
TILE_SW_T_NES:         Final[str] = 'sw_t_nes'       # Three sides face road
TILE_SW_T_NEW:         Final[str] = 'sw_t_new'
TILE_SW_T_NSW:         Final[str] = 'sw_t_nsw'
TILE_SW_T_ESW:         Final[str] = 'sw_t_esw'
TILE_SW_SURROUNDED:    Final[str] = 'sw_surrounded'  # All sides road → dedicated X tile

# Sidewalk road-adjacency bitmask → tile ID
SIDEWALK_BITMASK_TO_TILE: Final[dict] = {
    0:  TILE_SW_SURFACE,
    1:  TILE_SW_EDGE_W,
    2:  TILE_SW_EDGE_S,
    3:  TILE_SW_CORNER_SW,
    4:  TILE_SW_EDGE_E,
    5:  TILE_SW_SURFACE,       # E+W both road → unusual, use surface
    6:  TILE_SW_CORNER_SE,
    7:  TILE_SW_T_ESW,
    8:  TILE_SW_EDGE_N,
    9:  TILE_SW_CORNER_NW,
    10: TILE_SW_SURFACE,       # N+S both road → unusual, use surface
    11: TILE_SW_T_NSW,
    12: TILE_SW_CORNER_NE,
    13: TILE_SW_T_NEW,
    14: TILE_SW_T_NES,
    15: TILE_SW_SURROUNDED,
}

# ── Ground tile IDs ───────────────────────────────────────────────────────────
TILE_GROUND_LAND:  Final[str] = 'ground_land'
TILE_GROUND_WATER: Final[str] = 'ground_water'

# ── City zone types ───────────────────────────────────────────────────────────
ZONE_CBD:         Final[int] = 0   # Central Business District — dense grid
ZONE_MIDTOWN:     Final[int] = 1   # Mixed-use — moderate density
ZONE_RESIDENTIAL: Final[int] = 2   # Residential outskirts — sparse, cul-de-sacs

# ── Phase names ───────────────────────────────────────────────────────────────
PHASE_ZONES: Final[str] = 'zones'
PHASE_BLOCKS: Final[str] = 'blocks'
PHASE_PARKS:  Final[str] = 'parks'
PHASE_LOTS:   Final[str] = 'lots'
PHASE_CIVIC:  Final[str] = 'civic'

# ── Per-phase PRNG salts (XOR with master_seed) — new phases ─────────────────
SALT_BLOCKS: Final[int] = 0x789ABC
SALT_PARKS:  Final[int] = 0xA1B2C3
SALT_LOTS:   Final[int] = 0xD4E5F6
SALT_CIVIC:  Final[int] = 0xF1E2D3

# ── Block detection constants ─────────────────────────────────────────────────
BLOCK_EXTERIOR_ID: Final[int] = -1   # cells touching map edge (exterior region)

# ── Park placement constants ──────────────────────────────────────────────────
PARK_SMALL_BLOCK_MAX:         Final[int]   = 12    # legacy — kept for compat (unused in new parks.py)

# New park placement thresholds — prefer LARGE blocks for visible neighborhood parks
# Target: park should be at least 25 cells (50m×50m) to read as a real park on screen.
PARK_MIN_AREA:                Final[int]   = 20    # minimum block size to qualify as park
PARK_IDEAL_MIN:               Final[int]   = 25    # preferred minimum (will read clearly on screen)
PARK_IDEAL_MAX:               Final[int]   = 120   # maximum (don't make entire districts parks)
PARK_MAX_PER_ZONE:            Final[int]   = 2     # legacy default; parks.py computes dynamic cap at runtime
PARK_CBD_PROBABILITY:         Final[float] = 0.45  # CBD: plazas/squares from mid-size blocks
PARK_MIDTOWN_PROBABILITY:     Final[float] = 0.55  # Midtown: neighbourhood parks
PARK_RESIDENTIAL_PROBABILITY: Final[float] = 0.45  # Residential: street parks + gardens

# Legacy aliases kept for import compatibility
PARK_RESIDENTIAL_MIN_AREA:    Final[int]   = PARK_MIN_AREA
PARK_RESIDENTIAL_MAX_AREA:    Final[int]   = PARK_IDEAL_MAX

# ── Lot subdivision constants ─────────────────────────────────────────────────
LOT_MIN_WIDTH: Final[int] = 3   # minimum lot width in cells (30m at 10m/cell) — handles small blocks
LOT_MIN_DEPTH: Final[int] = 3   # minimum lot depth in cells

# ── Civic anchor constants ────────────────────────────────────────────────────
CIVIC_ANCHOR_RADIUS: Final[int] = 3   # connector density boost radius around anchor

# ── Tile roles (game layer) ────────────────────────────────────────────────────
# Defines traversability and gameplay function of each cell.
ROLE_WALKABLE_ROAD:      Final[str] = 'road'         # highway or connector — full encounter area
ROLE_WALKABLE_HIGHWAY:   Final[str] = 'highway'      # arterial — lower encounter (fast traffic)
ROLE_WALKABLE_ALLEY:     Final[str] = 'alley'        # dead-end connector — high danger
ROLE_WALKABLE_SIDEWALK:  Final[str] = 'sidewalk'     # low encounter, safe movement
ROLE_WALKABLE_PARK:      Final[str] = 'park'         # medium encounter, scenic
ROLE_WALKABLE_PLAZA:     Final[str] = 'plaza'        # roundabout / market square — Type B only
ROLE_BUILDING_CBD:       Final[str] = 'bldg_cbd'     # office / civic — obstacle
ROLE_BUILDING_MIDTOWN:   Final[str] = 'bldg_mid'     # shop / apartment — obstacle
ROLE_BUILDING_RESI:      Final[str] = 'bldg_resi'    # house — obstacle
ROLE_BUILDING_CIVIC:     Final[str] = 'bldg_civic'   # landmark building — obstacle
ROLE_WATER:              Final[str] = 'water'         # impassable
ROLE_EXTERIOR:           Final[str] = 'exterior'      # outside any city block — obstacle/void

# ── Building types (assigned to lots) ─────────────────────────────────────────
BLDG_OFFICE:      Final[str] = 'office'
BLDG_BANK:        Final[str] = 'bank'
BLDG_MARKET:      Final[str] = 'market'
BLDG_CIVIC_HALL:  Final[str] = 'civic_hall'      # at civic anchor
BLDG_SHOP:        Final[str] = 'shop'
BLDG_RESTAURANT:  Final[str] = 'restaurant'
BLDG_APARTMENT:   Final[str] = 'apartment'
BLDG_CLINIC:      Final[str] = 'clinic'
BLDG_HOUSE:       Final[str] = 'house'
BLDG_SCHOOL:      Final[str] = 'school'
BLDG_PARK_FEATURE: Final[str] = 'park_feature'   # fountain / bench cluster in park
BLDG_STATION:     Final[str] = 'station'          # train / transit station
BLDG_HOSPITAL:    Final[str] = 'hospital'
BLDG_POLICE:      Final[str] = 'police'
BLDG_EMPTY_LOT:   Final[str] = 'empty_lot'        # vacant / undeveloped

# CBD building type weights  [type, weight]
CBD_BLDG_WEIGHTS: Final[list] = [
    (BLDG_OFFICE,     40),
    (BLDG_BANK,       20),
    (BLDG_MARKET,     20),
    (BLDG_APARTMENT,  10),
    (BLDG_EMPTY_LOT,  10),
]
MIDTOWN_BLDG_WEIGHTS: Final[list] = [
    (BLDG_SHOP,       30),
    (BLDG_RESTAURANT, 25),
    (BLDG_APARTMENT,  25),
    (BLDG_CLINIC,     10),
    (BLDG_EMPTY_LOT,  10),
]
RESI_BLDG_WEIGHTS: Final[list] = [
    (BLDG_HOUSE,      50),
    (BLDG_SCHOOL,     15),
    (BLDG_SHOP,       15),
    (BLDG_APARTMENT,  10),
    (BLDG_EMPTY_LOT,  10),
]

# Waterfront building weights (blocks with direct water adjacency)
WATERFRONT_BLDG_WEIGHTS: Final[list] = [
    (BLDG_RESTAURANT,  35),
    (BLDG_MARKET,      25),
    (BLDG_APARTMENT,   20),
    (BLDG_STATION,     10),   # ferry terminal
    (BLDG_EMPTY_LOT,   10),
]

# ── Encounter probabilities per tile role ─────────────────────────────────────
# Base probability (applied on each step onto this tile type).
# Final chance = clamp((base + density_bonus) * zone_mult + zone_offset - civic_bonus, 0, 1)
ENCOUNTER_BASE: Final[dict] = {
    ROLE_WALKABLE_HIGHWAY:  0.08,   # arterials: fast traffic, lower exposure
    ROLE_WALKABLE_ROAD:     0.12,   # connector roads: standard street danger
    ROLE_WALKABLE_ALLEY:    0.30,   # dead-end alleys: most dangerous
    ROLE_WALKABLE_SIDEWALK: 0.05,   # well-lit pavement: safe
    ROLE_WALKABLE_PARK:     0.25,   # secluded green space: muggers, wildlife
    ROLE_WALKABLE_PLAZA:    0.0,    # plazas: Type B/scripted only
}
# Zone modifiers: (multiplier, additive_offset)
ENCOUNTER_ZONE_MOD: Final[dict] = {
    0: (1.40,  0.05),   # CBD — crime dense
    1: (1.00,  0.00),   # Midtown — baseline
    2: (0.65, -0.03),   # Residential — quieter
}
# Civic anchor safety radius (Chebyshev cells): subtract this from encounter_chance
ENCOUNTER_CIVIC_PENALTY: Final[float] = 0.06
ENCOUNTER_CIVIC_RADIUS:  Final[int]   = 3
# Density bonus coefficient: add (DENSITY_BONUS_K * density_score) to base
ENCOUNTER_DENSITY_K: Final[float] = 0.08

# Legacy alias kept for old code (removed from buildings.py pass 1)
ENCOUNTER_BY_ROLE: Final[dict] = ENCOUNTER_BASE
ENCOUNTER_ZONE_MULT: Final[dict] = {k: v[0] for k, v in ENCOUNTER_ZONE_MOD.items()}

# ── Coastal character types ────────────────────────────────────────────────────
COAST_TYPE_NONE:  Final[str] = ''        # inland / not on shoreline
COAST_TYPE_CLIFF: Final[str] = 'cliff'   # rocky impassable face
COAST_TYPE_BEACH: Final[str] = 'beach'   # sandy gradual shore (buildable)
COAST_TYPE_DOCK:  Final[str] = 'dock'    # man-made pier / harbour (buildable)

# Building types for coastal lots
BLDG_WAREHOUSE:  Final[str] = 'warehouse'   # dock-side storage
BLDG_PIER:       Final[str] = 'pier'        # fishing / ferry pier
BLDG_RESORT:     Final[str] = 'resort'      # beachfront hotel
BLDG_BEACH_BAR:  Final[str] = 'beach_bar'   # casual beach restaurant

# Beach lot weights
BEACH_BLDG_WEIGHTS: Final[list] = [
    (BLDG_RESORT,      30),
    (BLDG_RESTAURANT,  30),
    (BLDG_BEACH_BAR,   20),
    (BLDG_APARTMENT,   15),
    (BLDG_EMPTY_LOT,    5),
]

# Dock lot weights
DOCK_BLDG_WEIGHTS: Final[list] = [
    (BLDG_WAREHOUSE,   35),
    (BLDG_PIER,        25),
    (BLDG_MARKET,      20),
    (BLDG_STATION,     10),
    (BLDG_EMPTY_LOT,   10),
]

# ── Phase names (new) ─────────────────────────────────────────────────────────
PHASE_BUILDINGS: Final[str] = 'buildings'
SALT_BUILDINGS:  Final[int]  = 0xB1C2D3
