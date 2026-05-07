"""
map_builder/tile_registry.py
─────────────────────────────
Fully calibrated tile registry — all pixel_rect values are exact coordinates
extracted by sheet_analyzer.py from the live sprite sheets.

Sprite sheet layout summary
────────────────────────────
roads.png  (1448 × 1086 px)
  band 0  y=15   h=100  8 tiles  — flat diamond surface variants (connector road)
  band 1  y=124  h=100  8 tiles  — damage/decay variants (connector road decor)
  band 2  y=241  h=80  12 tiles  — road marking overlays (crosswalk, arrows, yield)
  band 3  y=344  h=98   9 tiles  — structural connectivity tiles (T, X, corner, straight)
  band 4  y=461  h=102  8 tiles  — elevated highway tiles (3-D raised deck)
  band 5  y=580  h=380  6 grps  — roundabout 3×3 grid + extra damage tiles
  band 6  y=989  h=64  12 tiles  — road props (cone, barrier, cabinets, lamps)

sidewalks.png  (1448 × 1086 px)
  band 0  y=37   h=102 10 tiles  — flat concrete surface variants
  band 1  y=168  h=114 10 tiles  — structural corners, T/X junctions (with curb)
  band 2  y=317  h=123  7 tiles  — straight edges, inner curves, roundabout arcs
  band 4  y=477  h=118  9 tiles  — small corners, ramps, tactile paving strips
  band 5  y=628  h=114 10 tiles  — tactile variants, grates, planters
  band 6  y=769  h=114 10 tiles  — worn/cracked concrete, utility covers
  band 7  y=901  h=130 15 tiles  — sidewalk props (debris, cone, bollards, bins, signs)

Connectivity convention (road and sidewalk bitmask)
────────────────────────────────────────────────────
  Bit 3 (8) = North   Bit 2 (4) = East
  Bit 1 (2) = South   Bit 0 (1) = West
  e.g. 0b1010 = N+S connected → straight N-S road
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .constants import (
    SHEET_ROADS, SHEET_SIDEWALKS,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    TILE_ROAD_ISOLATED,
    TILE_ROAD_END_W, TILE_ROAD_END_S, TILE_ROAD_CORNER_SW,
    TILE_ROAD_END_E, TILE_ROAD_STRAIGHT_EW, TILE_ROAD_CORNER_SE,
    TILE_ROAD_T_ESW, TILE_ROAD_END_N, TILE_ROAD_CORNER_NW,
    TILE_ROAD_STRAIGHT_NS, TILE_ROAD_T_NSW, TILE_ROAD_CORNER_NE,
    TILE_ROAD_T_NEW, TILE_ROAD_T_NES, TILE_ROAD_X,
    TILE_SW_SURFACE, TILE_SW_EDGE_N, TILE_SW_EDGE_E,
    TILE_SW_EDGE_S, TILE_SW_EDGE_W,
    TILE_SW_CORNER_NE, TILE_SW_CORNER_NW, TILE_SW_CORNER_SE, TILE_SW_CORNER_SW,
    TILE_SW_END_N, TILE_SW_END_E, TILE_SW_END_S, TILE_SW_END_W,
    TILE_SW_T_NES, TILE_SW_T_NEW, TILE_SW_T_NSW, TILE_SW_T_ESW,
    TILE_SW_SURROUNDED,
    TILE_GROUND_LAND, TILE_GROUND_WATER,
    ROAD_BITMASK_TO_TILE, SIDEWALK_BITMASK_TO_TILE,
)

# ── Tile definition ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TileDef:
    """
    Complete descriptor for a single sprite tile.

    pixel_rect    : (left, top, width, height) in pixels on the sprite sheet
    sprite_sheet  : 'roads' or 'sidewalks'
    category      : road category (highway / connector) or None for sidewalks
    is_damaged    : True for cracked / weathered variants
    label         : human-readable identifier for debugging
    """
    pixel_rect:   tuple[int, int, int, int]
    sprite_sheet: str
    category:     Optional[str] = None
    is_damaged:   bool          = False
    label:        str           = ''

    def get_rect(self) -> tuple[int, int, int, int]:
        return self.pixel_rect


# ── Shorthand constructors ────────────────────────────────────────────────────

def _r(left, top, w, h, label='', damaged=False, cat=ROAD_CONNECTOR) -> TileDef:
    return TileDef((left, top, w, h), SHEET_ROADS, cat, damaged, label)

def _hw(left, top, w, h, label='') -> TileDef:
    return TileDef((left, top, w, h), SHEET_ROADS, ROAD_HIGHWAY, False, label)

def _s(left, top, w, h, label='', damaged=False) -> TileDef:
    return TileDef((left, top, w, h), SHEET_SIDEWALKS, None, damaged, label)


# ═════════════════════════════════════════════════════════════════════════════
#  ROAD TILES
# ═════════════════════════════════════════════════════════════════════════════
#
# roads.png band 3 (y=344, h=98) — STRUCTURAL CONNECTIVITY TILES
# These are the primary road tiles placed by the algorithm.  Each tile's
# geometry encodes the connection pattern visually (which arms of the road
# extend in which direction).
#
# Band 3 tile order (left → right, 9 tiles):
#   [0] X-intersection (4-way, all connections)         → TILE_ROAD_X
#   [1] T-junction open N  (E+S+W connected)            → TILE_ROAD_T_ESW
#   [2] T-junction open W  (N+E+S connected)            → TILE_ROAD_T_NES
#   [3] T-junction open S  (N+E+W connected)            → TILE_ROAD_T_NEW
#   [4] T-junction open E  (N+S+W connected)            → TILE_ROAD_T_NSW
#   [5] Straight N-S                                    → TILE_ROAD_STRAIGHT_NS
#   [6] Corner NW  (N+W connected, curves NW)           → TILE_ROAD_CORNER_NW
#   [7] Corner NE  (N+E connected, curves NE)           → TILE_ROAD_CORNER_NE
#   [8] Straight E-W                                    → TILE_ROAD_STRAIGHT_EW
#
# roads.png band 0 (y=15, h=100) — SURFACE CONDITION VARIANTS (connector)
# Used as variation overlays on LAYER_DECOR and as primary surface for
# cells where a structural tile is not uniquely needed.
#
# Band 0 tile order:
#   [0] plain asphalt        [1] dashed center line
#   [2] yellow center line   [3] plain dark
#   [4] cracked light        [5] cracked heavy
#   [6] pothole              [7] flooded / puddle
#
# ─────────────────────────────────────────────────────────────────────────────

_ROAD_TILES: dict[str, list[TileDef]] = {

    # ── Structural connectivity — connector roads (band 3) ────────────────────
    TILE_ROAD_X: [
        _r(14,  344, 154, 98, 'X-intersection'),
    ],
    TILE_ROAD_T_ESW: [
        _r(174, 344, 146, 98, 'T open-N (E+S+W)'),
    ],
    TILE_ROAD_T_NES: [
        _r(331, 344, 153, 98, 'T open-W (N+E+S)'),
    ],
    TILE_ROAD_T_NEW: [
        _r(495, 344, 141, 98, 'T open-S (N+E+W)'),
    ],
    TILE_ROAD_T_NSW: [
        _r(651, 344, 144, 98, 'T open-E (N+S+W)'),
    ],
    TILE_ROAD_STRAIGHT_NS: [
        _r(812, 344, 142, 98, 'straight N-S'),
        _r(18,   15, 152, 100, 'straight N-S plain surface'),
        _r(184,  15, 151, 100, 'straight N-S dashed',   damaged=False),
    ],
    TILE_ROAD_STRAIGHT_EW: [
        _r(1260, 344, 118, 98, 'straight E-W'),
        _r(350,  15, 152, 100, 'straight E-W yellow line'),
    ],
    TILE_ROAD_CORNER_NW: [
        _r(968,  344, 138, 98, 'corner NW'),
    ],
    TILE_ROAD_CORNER_NE: [
        _r(1131, 344, 110, 98, 'corner NE'),
    ],
    # SE / SW: no dedicated sprite — reuse NE / NW with engine-side rotation flag
    # (or replace with exact tiles once sheet is extended)
    TILE_ROAD_CORNER_SE: [
        _r(1131, 344, 110, 98, 'corner SE (NE stand-in)'),
    ],
    TILE_ROAD_CORNER_SW: [
        _r(968,  344, 138, 98, 'corner SW (NW stand-in)'),
    ],

    # ── Dead-end caps — no dedicated sprite; use straight tile ────────────────
    TILE_ROAD_END_N: [
        _r(812, 344, 142, 98, 'end-cap N (straight stand-in)'),
    ],
    TILE_ROAD_END_S: [
        _r(812, 344, 142, 98, 'end-cap S (straight stand-in)'),
    ],
    TILE_ROAD_END_E: [
        _r(1260, 344, 118, 98, 'end-cap E (straight EW stand-in)'),
    ],
    TILE_ROAD_END_W: [
        _r(1260, 344, 118, 98, 'end-cap W (straight EW stand-in)'),
    ],
    TILE_ROAD_ISOLATED: [
        _r(18,   15, 152, 100, 'isolated road fallback'),
    ],

    # ── Highway structural tiles (band 4, elevated deck) ──────────────────────
    # Band 4 order (left → right, 8 tiles):
    #   [0] elevated straight N-S     [1] elevated T-junction
    #   [2] elevated X-junction       [3] elevated wide crossing
    #   [4] elevated plain N-S        [5-7] elevated straight variants
    TILE_ROAD_STRAIGHT_NS + '_hw': [
        _hw(19,  461, 142, 102, 'highway straight N-S elevated'),
        _hw(704, 461, 122, 102, 'highway straight N-S plain'),
        _hw(875, 461, 123, 102, 'highway straight variant'),
    ],
    TILE_ROAD_STRAIGHT_EW + '_hw': [
        _hw(1189, 461, 125, 102, 'highway straight E-W elevated'),
        _hw(1024, 461, 126, 102, 'highway straight E-W variant'),
    ],
    TILE_ROAD_T_NES + '_hw': [
        _hw(190, 461, 131, 102, 'highway T-junction elevated'),
    ],
    TILE_ROAD_T_ESW + '_hw': [
        _hw(190, 461, 131, 102, 'highway T-junction elevated (ESW stand-in)'),
    ],
    TILE_ROAD_T_NEW + '_hw': [
        _hw(190, 461, 131, 102, 'highway T-junction elevated (NEW stand-in)'),
    ],
    TILE_ROAD_T_NSW + '_hw': [
        _hw(190, 461, 131, 102, 'highway T-junction elevated (NSW stand-in)'),
    ],
    TILE_ROAD_X + '_hw': [
        _hw(347, 461, 137, 102, 'highway X-junction elevated'),
    ],
    TILE_ROAD_CORNER_NE + '_hw': [
        _hw(512, 461, 165, 102, 'highway corner/curve elevated'),
    ],
    TILE_ROAD_CORNER_NW + '_hw': [
        _hw(512, 461, 165, 102, 'highway corner elevated (NW stand-in)'),
    ],
    TILE_ROAD_CORNER_SE + '_hw': [
        _hw(512, 461, 165, 102, 'highway corner elevated (SE stand-in)'),
    ],
    TILE_ROAD_CORNER_SW + '_hw': [
        _hw(512, 461, 165, 102, 'highway corner elevated (SW stand-in)'),
    ],
    TILE_ROAD_END_N  + '_hw': [_hw(704, 461, 122, 102, 'highway end N')],
    TILE_ROAD_END_S  + '_hw': [_hw(704, 461, 122, 102, 'highway end S')],
    TILE_ROAD_END_E  + '_hw': [_hw(1189,461, 125, 102, 'highway end E')],
    TILE_ROAD_END_W  + '_hw': [_hw(1189,461, 125, 102, 'highway end W')],
    TILE_ROAD_ISOLATED + '_hw': [_hw(704, 461, 122, 102, 'highway isolated')],
}

# ── Road decor overlays (bands 0-2) — placed on LAYER_DECOR ──────────────────
# These are the surface condition / marking tiles placed on top of structural.

ROAD_DECOR_TILES: dict[str, TileDef] = {
    # Surface conditions (band 0/1)
    'road_surface_plain':        _r(18,   15,  152, 100, 'plain asphalt'),
    'road_surface_dashed':       _r(184,  15,  151, 100, 'dashed center line'),
    'road_surface_yellow':       _r(350,  15,  152, 100, 'yellow center line'),
    'road_surface_dark':         _r(514,  15,  152, 100, 'dark plain asphalt'),
    'road_crack_light':          _r(679,  15,  151, 100, 'cracked light',   damaged=True),
    'road_crack_heavy':          _r(842,  15,  152, 100, 'cracked heavy',   damaged=True),
    'road_pothole':              _r(1009, 15,  151, 100, 'pothole',         damaged=True),
    'road_puddle':               _r(1174, 15,  151, 100, 'flooded puddle',  damaged=True),
    'road_crack_deep_1':         _r(18,  124,  151, 100, 'deep crack 1',    damaged=True),
    'road_crack_deep_2':         _r(183, 124,  152, 100, 'deep crack 2',    damaged=True),
    'road_crater_wet':           _r(350, 124,  151, 100, 'crater + water',  damaged=True),
    'road_drain_1':              _r(514, 124,  152, 100, 'drain cover 1'),
    'road_drain_2':              _r(679, 124,  150, 100, 'drain cover 2'),
    'road_drain_3':              _r(843, 124,  151, 100, 'drain cover 3'),
    'road_skid_1':               _r(1008,124,  151, 100, 'skid marks 1',    damaged=True),
    'road_skid_2':               _r(1174,124,  151, 100, 'skid marks 2',    damaged=True),
    # Marking overlays (band 2)
    'road_marking_crosswalk':    _r(10,  241,  129, 80,  'crosswalk'),
    'road_marking_crosswalk_b':  _r(145, 241,  112, 80,  'crosswalk alt'),
    'road_marking_yield':        _r(263, 241,  113, 80,  'yield triangle'),
    'road_marking_yield_dots':   _r(385, 241,  111, 80,  'yield dots'),
    'road_marking_arrow_l':      _r(505, 241,  104, 80,  'turn arrow left'),
    'road_marking_arrow_r':      _r(615, 241,  103, 80,  'turn arrow right'),
    'road_marking_arrow_s':      _r(725, 241,  101, 80,  'arrow straight'),
    'road_marking_fork':         _r(832, 241,  101, 80,  'fork / diverge'),
    'road_marking_merge':        _r(940, 241,  101, 80,  'merge'),
    'road_marking_uturn':        _r(1047,241,  101, 80,  'U-turn'),
    'road_marking_dashes':       _r(1154,241,  101, 80,  'dashed lane'),
    'road_marking_dashes_b':     _r(1262,241,  101, 80,  'dashed lane alt'),
}

# Roundabout tiles — 3×3 multi-tile system
# Tile grid: col 0-2  ×  row 0-2.  Each cell ≈ 140 × 127 px.
_RB_X0, _RB_Y0 = 19,  580
_RB_CW, _RB_CH = 140, 127
ROUNDABOUT_TILES: dict[str, TileDef] = {
    f'roundabout_{row}_{col}': _r(
        _RB_X0 + col * _RB_CW,
        _RB_Y0 + row * _RB_CH,
        _RB_CW, _RB_CH,
        f'roundabout r{row}c{col}'
    )
    for row in range(3) for col in range(3)
}

# Road props (band 6)
ROAD_PROP_TILES: dict[str, TileDef] = {
    'prop_road_cone':        _r(28,  989, 92, 64, 'traffic cone'),
    'prop_road_drain_a':     _r(156, 989, 91, 64, 'drain cover A'),
    'prop_road_drain_b':     _r(275, 989, 91, 64, 'drain cover B'),
    'prop_road_barrier':     _r(402, 989, 83, 64, 'construction barrier'),
    'prop_road_cabinet_s':   _r(512, 989, 82, 64, 'small cabinet'),
    'prop_road_cabinet_l':   _r(616, 989, 94, 64, 'large cabinet'),
    'prop_road_postbox_red': _r(729, 989, 85, 64, 'red postbox'),
    'prop_road_postbox_blu': _r(845, 989, 80, 64, 'blue mailbox'),
    'prop_road_lamp_a':      _r(967, 989, 77, 64, 'street lamp A'),
    'prop_road_lamp_b':      _r(1085,989, 74, 64, 'street lamp B'),
    'prop_road_jersey_a':    _r(1209,989, 65, 64, 'jersey barrier A'),
    'prop_road_jersey_b':    _r(1317,989, 64, 64, 'jersey barrier B'),
}


# ═════════════════════════════════════════════════════════════════════════════
#  SIDEWALK TILES
# ═════════════════════════════════════════════════════════════════════════════
#
# sidewalks.png structural tiles come from band 1 and band 2.
#
# Band 1 (y=168, h=114) — 10 tiles — CORNERS, JUNCTIONS, EDGE
# Order (left → right):
#   [0] Outer corner NE   [1] Outer corner NW   [2] Outer corner SE
#   [3] Outer corner SW   [4] End cap (short)   [5] Straight edge
#   [6] T-junction NES    [7] T-junction NEW     [8] X (surrounded)
#   [9] T-junction NSW/ESW
#
# Band 2 (y=317, h=123) — 7 tiles — STRAIGHT EDGES (all 4 dirs) + ARCS
# Order:
#   [0] Edge S  [1] T ESW  [2] Inner corner  [3] Inner corner alt
#   [4] Arc     [5] Wide arcs (roundabout SW)  [6] Wide arc (roundabout SE)

_SIDEWALK_TILES: dict[str, list[TileDef]] = {

    # ── Surface tiles (LAYER_GROUND of sidewalk area, band 0) ─────────────────
    TILE_SW_SURFACE: [
        _s(28,   37, 139, 102, 'sw surface plain'),
        _s(179,  37, 137, 102, 'sw surface clean 2'),
        _s(327,  37, 138, 102, 'sw surface cracked light', damaged=True),
        _s(475,  37, 140, 102, 'sw surface cracked puddle', damaged=True),
        _s(628,  37, 137, 102, 'sw surface dirty'),
        _s(774,  37, 137, 102, 'sw surface wet puddle',    damaged=True),
    ],

    # ── Structural corner tiles (band 1) ──────────────────────────────────────
    TILE_SW_CORNER_NE: [
        _s(22,  168, 110, 114, 'sw corner NE outer'),
    ],
    TILE_SW_CORNER_NW: [
        _s(162, 168, 120, 114, 'sw corner NW outer'),
    ],
    TILE_SW_CORNER_SE: [
        _s(298, 168, 108, 114, 'sw corner SE outer'),
    ],
    TILE_SW_CORNER_SW: [
        _s(429, 168, 121, 114, 'sw corner SW outer'),
    ],

    # ── Structural edge tiles ─────────────────────────────────────────────────
    # Band 1 tile 5 = generic straight edge; band 2 tile 0 gives an alt direction.
    TILE_SW_EDGE_N: [
        _s(661, 168, 122, 114, 'sw edge N'),
    ],
    TILE_SW_EDGE_S: [
        _s(25,  317, 150, 123, 'sw edge S'),
    ],
    TILE_SW_EDGE_E: [
        _s(196, 317, 171, 123, 'sw edge E / T-alt'),
    ],
    TILE_SW_EDGE_W: [
        _s(661, 168, 122, 114, 'sw edge W (N stand-in)'),
    ],

    # ── T-junction tiles (band 1 + 2) ─────────────────────────────────────────
    TILE_SW_T_NES: [
        _s(791, 168, 140, 114, 'sw T NES (open W)'),
    ],
    TILE_SW_T_NEW: [
        _s(954, 168, 139, 114, 'sw T NEW (open S)'),
    ],
    TILE_SW_T_NSW: [
        _s(1286,168, 128, 114, 'sw T NSW (open E)'),
    ],
    TILE_SW_T_ESW: [
        _s(196, 317, 171, 123, 'sw T ESW (open N)'),
    ],

    # ── X-intersection (surrounded by road on all sides) ─────────────────────
    TILE_SW_SURROUNDED: [
        _s(1132,168, 132, 114, 'sw X surrounded'),
    ],

    # ── End-cap tiles (band 1 tile 4 — short end piece) ──────────────────────
    TILE_SW_END_N: [
        _s(579, 168,  58, 114, 'sw end cap N'),
    ],
    TILE_SW_END_S: [
        _s(579, 168,  58, 114, 'sw end cap S (N stand-in)'),
    ],
    TILE_SW_END_E: [
        _s(579, 168,  58, 114, 'sw end cap E (N stand-in)'),
    ],
    TILE_SW_END_W: [
        _s(579, 168,  58, 114, 'sw end cap W (N stand-in)'),
    ],
}

# Sidewalk surface decor overlays (bands 5-6)
SIDEWALK_DECOR_TILES: dict[str, TileDef] = {
    # Drain covers (band 0)
    'sw_drain_sq':          _s(921,  37, 137, 102, 'drain square cover'),
    'sw_drain_rd':          _s(1065, 37, 125, 102, 'drain round cover'),
    'sw_grate_rd':          _s(1199, 37, 127, 102, 'grate round'),
    'sw_grate_sq':          _s(1329, 37, 104, 102, 'grate square'),
    # Tactile paving (band 4)
    'sw_tactile_wide_a':    _s(745,  477, 243, 118, 'tactile paving wide A'),
    'sw_tactile_strip_a':   _s(1003, 477, 138, 118, 'tactile strip A'),
    'sw_tactile_strip_b':   _s(1159, 477, 131, 118, 'tactile strip B'),
    'sw_tactile_strip_c':   _s(1301, 477, 126, 118, 'tactile strip C'),
    # Tactile surface tiles (band 5)
    'sw_tactile_ns_ylw':    _s(32,   628, 132, 114, 'tactile NS yellow'),
    'sw_tactile_ew_ylw':    _s(184,  628, 122, 114, 'tactile EW yellow'),
    'sw_tactile_ns_red':    _s(323,  628, 117, 114, 'tactile NS red'),
    'sw_tactile_ew_red':    _s(456,  628, 105, 114, 'tactile EW red'),
    'sw_grate_vent_a':      _s(576,  628, 110, 114, 'vent grate A'),
    'sw_grate_vent_b':      _s(703,  628, 120, 114, 'vent grate B'),
    # Planters (band 5)
    'sw_planter_clean':     _s(855,  628, 116, 114, 'planter clean'),
    'sw_planter_tagged':    _s(998,  628, 114, 114, 'planter tagged'),
    # Stain overlays (band 5)
    'sw_stain_a':           _s(1125, 628, 140, 114, 'stain A'),
    'sw_stain_b':           _s(1283, 628, 141, 114, 'stain B'),
    # Worn concrete variants (band 6)
    'sw_crack_a':           _s(32,   769, 132, 114, 'concrete crack A',    damaged=True),
    'sw_crack_b':           _s(178,  769, 125, 114, 'concrete crack B',    damaged=True),
    'sw_concrete_alt':      _s(314,  769, 131, 114, 'concrete alt finish'),
    'sw_utility_panel':     _s(458,  769, 125, 114, 'utility panel'),
    'sw_manhole_rd':        _s(597,  769, 123, 114, 'manhole round'),
    'sw_access_sq':         _s(731,  769, 120, 114, 'access panel square'),
    'sw_worn_a':            _s(863,  769, 126, 114, 'worn concrete A',     damaged=True),
    'sw_worn_b':            _s(1000, 769, 124, 114, 'worn concrete B',     damaged=True),
    'sw_worn_c':            _s(1133, 769, 130, 114, 'worn concrete C',     damaged=True),
    'sw_growth':            _s(1275, 769, 138, 114, 'weed growth',         damaged=True),
}

# Sidewalk props (band 7)
SIDEWALK_PROP_TILES: dict[str, TileDef] = {
    'prop_sw_rubble_lg':    _s(37,   901,  84, 130, 'rubble large'),
    'prop_sw_rubble_sm':    _s(165,  901,  59, 130, 'rubble small'),
    'prop_sw_debris':       _s(254,  901,  53, 130, 'litter debris'),
    'prop_sw_paper':        _s(333,  901,  27, 130, 'newspaper'),
    'prop_sw_cone':         _s(404,  901,  60, 130, 'traffic cone'),
    'prop_sw_barrier':      _s(485,  901,  55, 130, 'warning barrier'),
    'prop_sw_box_elec':     _s(585,  901,  68, 130, 'electrical box'),
    'prop_sw_box_gray':     _s(694,  901,  65, 130, 'gray cabinet'),
    'prop_sw_box_red':      _s(807,  901,  61, 130, 'red box'),
    'prop_sw_box_blue':     _s(910,  901,  62, 130, 'blue box'),
    'prop_sw_bollard_a':    _s(1016, 901,  29, 130, 'bollard A'),
    'prop_sw_bollard_b':    _s(1101, 901,  31, 130, 'bollard B ornate'),
    'prop_sw_sign_a':       _s(1188, 901,  27, 130, 'street sign A'),
    'prop_sw_sign_b':       _s(1273, 901,  27, 130, 'street sign B'),
    'prop_sw_bin':          _s(1343, 901,  54, 130, 'trash bin'),
}

# ── Ground tiles ──────────────────────────────────────────────────────────────
_GROUND_TILES: dict[str, list[TileDef]] = {
    TILE_GROUND_LAND: [
        _s(28,  37, 139, 102, 'ground land'),
    ],
    TILE_GROUND_WATER: [
        _s(774, 37, 137, 102, 'ground water (blue puddle stand-in)'),
    ],
}


# ═════════════════════════════════════════════════════════════════════════════
#  REGISTRY
# ═════════════════════════════════════════════════════════════════════════════

class TileRegistry:
    """
    Unified access point for all tile definitions.

    Road tiles, sidewalk tiles, ground tiles, decor tiles and props are all
    registered here.  The generator calls resolve_road_tile_id() and
    resolve_sidewalk_tile_id() to pick the correct tile for each bitmask.
    The renderer calls get_variants() to get the list of TileDef objects,
    then indexes into it with the cell's stored variation index.
    """

    def __init__(self) -> None:
        self._tiles: dict[str, list[TileDef]] = {}
        self._tiles.update(_ROAD_TILES)
        self._tiles.update(_SIDEWALK_TILES)
        self._tiles.update(_GROUND_TILES)
        # Flat decor / prop registrations (single-variant)
        for tid, tdef in {**ROAD_DECOR_TILES, **ROUNDABOUT_TILES,
                          **ROAD_PROP_TILES, **SIDEWALK_DECOR_TILES,
                          **SIDEWALK_PROP_TILES}.items():
            self._tiles[tid] = [tdef]

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_variants(self, tile_id: str) -> list[TileDef]:
        return self._tiles.get(tile_id, [])

    def has_tile(self, tile_id: str) -> bool:
        return bool(self._tiles.get(tile_id))

    # ── Road tile resolution ──────────────────────────────────────────────────

    def resolve_road_tile_id(self, bitmask: int, category: str) -> str:
        base_id = ROAD_BITMASK_TO_TILE.get(bitmask, TILE_ROAD_ISOLATED)
        if category == ROAD_HIGHWAY:
            hw_id = base_id + '_hw'
            if self.has_tile(hw_id):
                return hw_id
        return base_id

    # ── Sidewalk tile resolution ──────────────────────────────────────────────

    def resolve_sidewalk_tile_id(self, road_adjacency_bitmask: int) -> str:
        return SIDEWALK_BITMASK_TO_TILE.get(road_adjacency_bitmask, TILE_SW_SURFACE)

    # ── Decor tile list (for decoration phase) ────────────────────────────────

    def road_decor_ids(self, damaged_only: bool = False) -> list[str]:
        ids = list(ROAD_DECOR_TILES.keys())
        if damaged_only:
            ids = [t for t in ids if ROAD_DECOR_TILES[t].is_damaged]
        return ids

    def sidewalk_decor_ids(self, damaged_only: bool = False) -> list[str]:
        ids = list(SIDEWALK_DECOR_TILES.keys())
        if damaged_only:
            ids = [t for t in ids if SIDEWALK_DECOR_TILES[t].is_damaged]
        return ids

    # ── All prop IDs ──────────────────────────────────────────────────────────

    def road_prop_ids(self) -> list[str]:
        return list(ROAD_PROP_TILES.keys())

    def sidewalk_prop_ids(self) -> list[str]:
        return list(SIDEWALK_PROP_TILES.keys())

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> str:
        lines = ['TileRegistry — calibrated tiles:']
        for tid in sorted(self._tiles):
            n = len(self._tiles[tid])
            r = self._tiles[tid][0].pixel_rect if n else '-'
            lines.append(f'  {tid:40s}  {n} var  {r}')
        return '\n'.join(lines)


# Module-level singleton
REGISTRY = TileRegistry()
