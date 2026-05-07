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
