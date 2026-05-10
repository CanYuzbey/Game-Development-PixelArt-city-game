"""
app.py — Visual Map Generation Demo
─────────────────────────────────────
Interactive Pygame window that renders the procedural map generator in real-time.
Watching the coastline, highways, connectors and sidewalks appear step-by-step
is the fastest way to understand what the algorithm is doing.

Run:
    python app.py
    python app.py --seed 42 --coast west --width 64 --height 48

Controls:
    SPACE       — generate a new map (auto-increments seed)
    R           — regenerate the same seed (determinism test)
    1 .. 9      — jump to that seed directly
    H           — cycle coast direction  (none → N → S → E → W → random → none)
    +  / =      — zoom in
    -           — zoom out
    Arrow keys  — pan when zoomed in
    Q / Esc     — quit

Visual legend (bottom HUD):
    ■ blue      water
    ■ tan       bare land
    ■ gold      highway
    ■ cyan      connector road
    ■ grey      sidewalk
    ■ red dot   decor overlay (crack / puddle)

Sprint 6 — Visual Naturalism:
    Per-cell micro-variation, building shadows, shore gradient, road markings,
    park texture, exterior noise, water depth, smooth scaling.
"""
from __future__ import annotations
import sys, io, time, argparse, random as _random

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pygame

from map_builder             import MapGenerator, MapConfig, PHASE_COMPLETE
from map_builder.constants   import (
    LAYER_DECOR,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    PHASE_COASTLINE, PHASE_HIGHWAY, PHASE_CONNECTOR,
    PHASE_SIDEWALK, PHASE_ZONES, PHASE_BUILDINGS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN, ROLE_BUILDING_RESI, ROLE_BUILDING_CIVIC,
    ROLE_WALKABLE_ALLEY, ROLE_WALKABLE_PLAZA, ROLE_WALKABLE_HIGHWAY, ROLE_WALKABLE_PARK,
)
from map_builder.phases.elevation import PHASE_ELEVATION


# ── Colour palette ─────────────────────────────────────────────────────────────

C_BG          = ( 14,  16,  20)   # window background (deep navy)
C_UNINIT      = ( 25,  27,  33)   # un-generated cell

# ── Master palette (Sprint 6 — OSM/Google Maps calibrated + naturalness tuning) ─
C_WATER        = (106, 159, 191)   # OSM ocean — muted steel blue (mid depth)
C_WATER_SHALLOW= (138, 185, 200)   # shallow near shore — lighter, slightly green
C_WATER_DEEP   = ( 82, 130, 165)   # deep water away from shore — darker blue
C_LAND         = (180, 165, 138)   # vacant lot / exterior — dusty warm tan
C_HIGHWAY      = (220, 194, 120)   # OSM motorway gold-yellow
C_HW_CENTER    = (235, 215, 145)   # highway center-line stripe — lighter than road
C_CONNECTOR    = (178, 168, 152)   # local connector — darker than sidewalk (was 195,187,172)
C_SIDEWALK     = (200, 196, 188)   # pavement — slightly lighter than connector
C_GRID         = ( 22,  24,  30)   # inter-cell grid line
C_HUD_BG       = ( 10,  12,  18)   # HUD background strip
C_HUD_TEXT     = (215, 215, 215)   # primary HUD text
C_HUD_DIM      = (110, 110, 120)   # secondary / dim HUD text
C_PROGRESS_BG  = ( 35,  37,  48)   # progress bar background
C_PROGRESS_FG  = ( 55, 185, 110)   # progress bar fill (green)

# Zone-tinted exterior land colours (zone mode)
C_LAND_CBD         = (185, 175, 152)   # urban hardscape concrete
C_LAND_MIDTOWN     = (172, 178, 150)   # grey-green transitional
C_LAND_RESIDENTIAL = (152, 175, 130)   # residential setback / lawn

# Park — saturated green so it reads as park even in a grey urban field
C_PARK             = (106, 158,  74)   # Team 6 §2: primary park grass (OSM-matched)
C_PARK_LIGHT       = (130, 175,  96)   # sunlit / interior park variant
C_CIVIC            = (195,  65,  55)   # civic anchor — strong warm red

# Buildings — Sprint 6 calibrated to real map references
C_BLDG_CBD         = ( 82,  90, 100)   # dark blue-grey glass tower (OSM building dark)
C_BLDG_MIDTOWN     = (148, 108,  88)   # brick red-brown — EU mid-rise
C_BLDG_RESI        = (215, 188, 155)   # cream/tan suburban house — warm (was 210,185,155)
C_BLDG_CIVIC       = (195, 185, 155)   # pale limestone — classical civic
C_LANDMARK         = (158, 148, 115)   # darker stone landmark accent
C_ALLEY            = (162, 155, 145)   # service alley — darker than sidewalk
C_PLAZA            = (210, 205, 192)   # open plaza/market — light stone pavement
C_BEACH_SAND       = (215, 195, 155)   # warm beach/shore sand strip (existing shore gradient)

# Coastal character colours (Sprint 7)
C_CLIFF        = (105,  95,  82)   # dark rocky grey-brown — impassable coast
C_CLIFF_EDGE   = ( 78,  70,  60)   # darker edge on water side
C_BEACH_SAND_W = (225, 208, 165)   # wide beach — warm sandy yellow
C_BEACH_WET    = (195, 182, 142)   # wet sand near waterline
C_DOCK_PLANKS  = (138, 108,  72)   # weathered wooden pier planks
C_DOCK_PILINGS = (105,  82,  58)   # dark pier pilings

# ── Per-lot deterministic color variation (Team 7 research, §1) ───────────────
# Uses a 3-tap LCG so R/G/B channels are independently varied.
# Same lot_id always produces the same color — deterministic across seeds.
_LCG_PRIMES = (1_664_525, 22_695_477, 214_013)
_LCG_ADDS   = (1_013_904_223, 1_664_525, 6_364_136_223)
_LCG_MASK   = 0xFFFF_FFFF

# Per-zone variation range (max delta per channel, 0–255)
_LOT_ZONE_VAR = {
    ZONE_CBD:          20,   # tight — density does the work
    ZONE_MIDTOWN:      28,   # moderate brick/concrete variety
    ZONE_RESIDENTIAL:  34,   # warm variation — age, materials
}

# Per-zone cell micro-variation strength (±channels within a single lot)
_CELL_MICRO_VAR = {
    ZONE_CBD:          4,
    ZONE_MIDTOWN:      6,
    ZONE_RESIDENTIAL:  8,
}


def _cell_micro_var(base: tuple, cell_id: int, strength: int = 6) -> tuple:
    """Tiny deterministic per-cell noise within a lot — breaks up flat color patches."""
    h  = (cell_id * 2246822519 + 374761393)  & 0xFFFFFFFF
    h2 = (h        * 2246822519 + 374761393)  & 0xFFFFFFFF
    h3 = (h2       * 2246822519 + 374761393)  & 0xFFFFFFFF
    dr = ((h  & 0xFF) / 255.0 * 2 - 1) * strength
    dg = ((h2 & 0xFF) / 255.0 * 2 - 1) * strength
    db = ((h3 & 0xFF) / 255.0 * 2 - 1) * strength
    r, g, b = base
    return (
        max(10, min(255, int(r + dr))),
        max(10, min(255, int(g + dg))),
        max(10, min(255, int(b + db))),
    )


def _lot_varied_color(base: tuple, lot_id: int, density: float = 0.5,
                      zone_id: int = ZONE_MIDTOWN) -> tuple:
    """
    Deterministic per-lot color variation using a fast 3-tap LCG.
    CBD buildings darken/blue-shift under high density.
    Residential buildings warm up at low density.
    """
    # Three independent noise values in [-1, 1]
    seeds = [((lot_id * _LCG_PRIMES[i] + _LCG_ADDS[i]) & _LCG_MASK) for i in range(3)]
    noise = [(s / _LCG_MASK) * 2.0 - 1.0 for s in seeds]

    var = _LOT_ZONE_VAR.get(zone_id, 25)
    r, g, b = base
    dr = noise[0] * var
    dg = noise[1] * var
    db = noise[2] * var

    if zone_id == ZONE_CBD:
        # Denser CBD blocks → darker + slightly bluer (glass towers)
        dark = density * 28
        dr -= dark;  dg -= dark;  db += density * 15
    elif zone_id == ZONE_RESIDENTIAL:
        # Sparser residential → warmer (house materials, painted brick)
        warmth = (1.0 - density) * 22
        dr += warmth;  dg += warmth * 0.4;  db -= warmth * 0.3

    return (
        max(18, min(255, int(r + dr))),
        max(18, min(255, int(g + dg))),
        max(18, min(255, int(b + db))),
    )

# Phase accent colours for the progress bar
C_PHASE = {
    PHASE_COASTLINE:   ( 38, 120, 210),
    PHASE_ELEVATION:   ( 80, 160,  80),
    PHASE_ZONES:       (180, 130,  80),
    PHASE_HIGHWAY:     (235, 185,  45),
    PHASE_CONNECTOR:   ( 55, 195, 220),
    PHASE_SIDEWALK:    (155, 152, 142),
    PHASE_BUILDINGS:   ( 78,  86, 105),
    PHASE_COMPLETE:    ( 60, 185, 115),
    'blocks':          (100, 160, 200),
    'parks':           ( 72, 140,  72),
    'lots':            (180, 140, 100),
    'civic':           (255,  80,  80),
}

# Coast cycle list (for H key)
_COASTS = ['none', 'north', 'south', 'east', 'west', 'random']

# Zone colour mode toggle (Z key)
_zone_mode: bool = False

_ZONE_COLORS = {
    ZONE_CBD:         C_LAND_CBD,
    ZONE_MIDTOWN:     C_LAND_MIDTOWN,
    ZONE_RESIDENTIAL: C_LAND_RESIDENTIAL,
}

# ── Layout constants ───────────────────────────────────────────────────────────

WIN_W  = 1100
WIN_H  = 740
HUD_H  = 90          # pixels reserved for the bottom HUD strip
GRID_H = WIN_H - HUD_H


# ── Helpers ────────────────────────────────────────────────────────────────────

def cell_color(cell, row: int = 0, col: int = 0, grid=None) -> tuple[int, int, int]:
    """
    Return the display colour for one MapCell.

    Priority order (highest first):
      water → road → landmark → civic → park → sidewalk → building → exterior land

    Sprint 6: accepts optional row/col/grid for per-cell micro-variation,
    shore gradients, water depth, and exterior land noise.
    grid=None means skip all neighbour-dependent effects (backward-compatible).
    """
    # ── Water ─────────────────────────────────────────────────────────────────
    if cell.is_water:
        if grid is None:
            return C_WATER
        # Task 8 + Task 3: water depth gradient based on distance to land
        # Check 4 direct neighbours for land (shallow)
        nbrs_direct = [
            grid.cell(row - 1, col),
            grid.cell(row + 1, col),
            grid.cell(row, col - 1),
            grid.cell(row, col + 1),
        ]
        if any(n is not None and n.is_land for n in nbrs_direct):
            return C_WATER_SHALLOW
        # Check radius-2 neighbours for mid-depth
        nbrs_r2 = [
            grid.cell(row - 2, col), grid.cell(row + 2, col),
            grid.cell(row, col - 2), grid.cell(row, col + 2),
            grid.cell(row - 1, col - 1), grid.cell(row - 1, col + 1),
            grid.cell(row + 1, col - 1), grid.cell(row + 1, col + 1),
        ]
        if any(n is not None and n.is_land for n in nbrs_r2):
            return C_WATER
        return C_WATER_DEEP

    # ── Roads ────────────────────────────────────────────────────────────────
    if cell.is_road:
        tile_role = getattr(cell, 'tile_role', '')
        if tile_role == ROLE_WALKABLE_PLAZA:
            return C_PLAZA
        if tile_role == ROLE_WALKABLE_ALLEY:
            return C_ALLEY
        if cell.road_category == ROAD_HIGHWAY:
            return C_HIGHWAY
        return C_CONNECTOR

    if not cell.is_land:
        return C_UNINIT

    tile_role = getattr(cell, 'tile_role', '')
    lot_id    = getattr(cell, 'lot_id', -1)
    density   = getattr(cell, 'density_score', 0.5)

    # ── Civic anchor (the single central red marker) ────────────────────────
    if getattr(cell, 'is_civic_anchor', False):
        return C_CIVIC

    # ── Coastal character (cliff / beach / dock) ─────────────────────────────
    coast_type = getattr(cell, 'coast_type', '')
    if coast_type == 'cliff':
        if grid is not None:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = row + dr, col + dc
                if 0 <= nr < grid.height and 0 <= nc < grid.width:
                    if grid[nr][nc].is_water:
                        return C_CLIFF_EDGE
        return C_CLIFF

    if coast_type == 'beach':
        if grid is not None:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = row + dr, col + dc
                if 0 <= nr < grid.height and 0 <= nc < grid.width:
                    if grid[nr][nc].is_water:
                        return C_BEACH_WET
        cell_id = row * 1000 + col
        h = (cell_id * 1664525 + 1013904223) & 0xFFFFFFFF
        shift = ((h & 0x1F) - 16)
        base = C_BEACH_SAND_W
        return (
            max(180, min(240, base[0] + shift)),
            max(165, min(225, base[1] + shift)),
            max(120, min(195, base[2] + shift)),
        )

    if coast_type == 'dock':
        if (row + col) % 3 == 0:
            return C_DOCK_PILINGS
        cell_id = row * 1000 + col
        h = (cell_id * 22695477 + 1013904223) & 0xFFFFFFFF
        shift = ((h & 0xF) - 8)
        base = C_DOCK_PLANKS
        return (
            max(90,  min(180, base[0] + shift)),
            max(70,  min(145, base[1] + shift)),
            max(40,  min(110, base[2] + shift)),
        )

    # ── Parks — always green (checked BEFORE sidewalk) ───────────────────────
    if getattr(cell, 'is_park', False):
        # Task 5: park edge effect — lighter near road/sidewalk
        if grid is not None:
            nbrs = [
                grid.cell(row - 1, col), grid.cell(row + 1, col),
                grid.cell(row, col - 1), grid.cell(row, col + 1),
            ]
            if any(n is not None and (n.is_road or n.is_sidewalk) for n in nbrs):
                return C_PARK_LIGHT
        # Two-tone grass: deterministic per-cell
        cell_id = row * 1000 + col
        h = (cell_id * 1664525 + 1013904223) & 0xFFFFFFFF
        return C_PARK_LIGHT if (h & 1) else C_PARK

    # ── Residential setback / front yard ─────────────────────────────────────
    if getattr(cell, 'is_setback', False):
        if getattr(cell, 'near_park', False):
            return C_PARK
        return (188, 195, 160)

    # ── Sidewalk — Task 7: subtle paving variation ────────────────────────────
    if cell.is_sidewalk:
        cell_id = row * 1000 + col
        h = (cell_id * 1664525 + 1013904223) & 0xFFFFFFFF
        shift = ((h & 0x1F) - 16)
        base = C_SIDEWALK
        return (
            max(160, min(220, base[0] + shift)),
            max(160, min(220, base[1] + shift)),
            max(160, min(220, base[2] + shift)),
        )

    # ── Building lots — per-lot + per-cell colour variation ──────────────────
    zone_id = getattr(cell, 'zone_id', ZONE_MIDTOWN)
    cell_id = row * 1000 + col

    if tile_role == ROLE_BUILDING_CIVIC:
        base = _lot_varied_color(C_BLDG_CIVIC, lot_id, density, ZONE_CBD) if lot_id >= 0 else C_BLDG_CIVIC
        return _cell_micro_var(base, cell_id, _CELL_MICRO_VAR.get(ZONE_CBD, 4))

    if tile_role == ROLE_BUILDING_CBD:
        base = _lot_varied_color(C_BLDG_CBD, lot_id, density, ZONE_CBD) if lot_id >= 0 else C_BLDG_CBD
        return _cell_micro_var(base, cell_id, _CELL_MICRO_VAR.get(ZONE_CBD, 4))

    if tile_role == ROLE_BUILDING_MIDTOWN:
        base = _lot_varied_color(C_BLDG_MIDTOWN, lot_id, density, ZONE_MIDTOWN) if lot_id >= 0 else C_BLDG_MIDTOWN
        return _cell_micro_var(base, cell_id, _CELL_MICRO_VAR.get(ZONE_MIDTOWN, 6))

    if tile_role == ROLE_BUILDING_RESI:
        base = _lot_varied_color(C_BLDG_RESI, lot_id, density, ZONE_RESIDENTIAL) if lot_id >= 0 else C_BLDG_RESI
        return _cell_micro_var(base, cell_id, _CELL_MICRO_VAR.get(ZONE_RESIDENTIAL, 8))

    # ── Courtyard / L-shape interior plazas ──────────────────────────────────
    if tile_role == ROLE_WALKABLE_PLAZA and lot_id >= 0:
        return C_PLAZA

    # ── Exterior land (unpaved, outside blocks) ──────────────────────────────
    elevation = getattr(cell, 'elevation', 0.5)
    if _zone_mode:
        base = _ZONE_COLORS.get(cell.zone_id, C_LAND)
        factor = 0.6 + 0.4 * density
        base_color = tuple(min(255, int(ch * factor)) for ch in base)
        # Task 9: zone colour softening — blend at zone boundaries
        if grid is not None:
            nbrs = [
                grid.cell(row - 1, col), grid.cell(row + 1, col),
                grid.cell(row, col - 1), grid.cell(row, col + 1),
            ]
            for n in nbrs:
                if n is not None and n.is_land and n.zone_id != cell.zone_id and n.zone_id in _ZONE_COLORS:
                    cell_hash = (row * 1000 + col) * 2654435761 & 0xFFFFFFFF
                    if (cell_hash & 0xFF) < 38:  # ~15% of cells get blended
                        nbr_c = _ZONE_COLORS[n.zone_id]
                        base_color = (
                            int(base_color[0] * 0.85 + nbr_c[0] * 0.15),
                            int(base_color[1] * 0.85 + nbr_c[1] * 0.15),
                            int(base_color[2] * 0.85 + nbr_c[2] * 0.15),
                        )
                        break
    else:
        base_color = C_LAND
        # Task 3: shore gradient — land cells adjacent to water get sandy tint
        if grid is not None:
            nbrs = [
                grid.cell(row - 1, col), grid.cell(row + 1, col),
                grid.cell(row, col - 1), grid.cell(row, col + 1),
            ]
            if any(n is not None and n.is_water for n in nbrs):
                base_color = (
                    int(base_color[0] * 0.75 + C_BEACH_SAND[0] * 0.25),
                    int(base_color[1] * 0.75 + C_BEACH_SAND[1] * 0.25),
                    int(base_color[2] * 0.75 + C_BEACH_SAND[2] * 0.25),
                )

    # Task 6: exterior land 3-tone noise (grass / gravel / concrete patches)
    cell_id_ext = row * 1000 + col
    h_ext = (cell_id_ext * 22695477 + 1) & 0xFFFFFFFF
    frac = (h_ext & 0xFFFF) / 65535.0
    if frac < 0.30:
        base_color = (
            int(base_color[0] * 0.95),
            min(255, int(base_color[1] * 1.04)),
            int(base_color[2] * 0.92),
        )
    elif frac > 0.75:
        avg = (base_color[0] + base_color[1] + base_color[2]) // 3
        base_color = (avg + 8, avg + 6, avg + 4)

    # Subtle elevation tint: +8 brightness on hilltops, -6 in valleys
    if elevation > 0.65:
        elev_shift = int(8 * (elevation - 0.65) / 0.35)
        return tuple(min(255, ch + elev_shift) for ch in base_color)
    elif elevation < 0.35:
        elev_shift = int(6 * (0.35 - elevation) / 0.35)
        return tuple(max(10, ch - elev_shift) for ch in base_color)
    return base_color



def build_config(seed: int, coast: str, width: int, height: int) -> MapConfig:
    return MapConfig(
        width              = width,
        height             = height,
        master_seed        = seed,
        coast_side         = coast,
        coast_coverage     = 0.28,
        highway_ns_min     = 2,
        highway_ns_max     = 4,
        highway_ew_min     = 0,
        highway_ew_max     = 2,
        highway_organic    = 0.25,
        # Sprint 3: wider spacing → realistic city block sizes
        #   connector_spacing=12 → 120m E-W block depth (Manhattan ~80m, Paris ~60m)
        #   avenue_spacing=24   → 240m N-S corridor  (real NYC avenue spacing ~270m)
        connector_density  = 0.65,
        connector_spacing  = 8,    # Sprint 3: 80m E-W block depth — realistic dense urban
        avenue_spacing     = 18,   # 180m N-S corridor — EU/Asian city block scale
        min_block_depth    = 2,
        connector_turn_bias  = 0.08,
        roundabout_count     = 8,
        diagonal_streets     = 2,
        sidewalk_damage_rate = 0.15,
    )


# ── Main app ───────────────────────────────────────────────────────────────────

class MapApp:

    def __init__(self, seed: int, coast: str, width: int, height: int) -> None:
        pygame.init()
        pygame.display.set_caption('Map Builder — Visual Demo')
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock  = pygame.time.Clock()
        try:
            self.font_sm = pygame.font.SysFont('Consolas', 13)
            self.font_md = pygame.font.SysFont('Consolas', 15, bold=True)
            self.font_lg = pygame.font.SysFont('Consolas', 18, bold=True)
        except Exception:
            self.font_sm = self.font_md = self.font_lg = pygame.font.Font(None, 16)

        # Generation state
        self.seed        = seed
        self.coast_idx   = _COASTS.index(coast) if coast in _COASTS else 0
        self.width       = width
        self.height      = height
        self.generator   = None
        self.gen_iter    = None
        self.progress    = None          # last GeneratorProgress
        self.done        = False
        self.gen_time    = 0.0
        self.stats: dict = {}

        # View state
        self.zoom        = 1.0           # 1.0 = fit grid to window
        self.pan_x       = 0             # pixel offset
        self.pan_y       = 0

        # Pre-render surface (one pixel per cell)
        self.cell_surf: pygame.Surface | None = None
        self._build_cell_surf()

        self._start_generation()

    # ── Generation ────────────────────────────────────────────────────────────

    def _start_generation(self) -> None:
        coast = _COASTS[self.coast_idx]
        config          = build_config(self.seed, coast, self.width, self.height)
        self.generator  = MapGenerator(config)
        self.gen_iter   = self.generator.generate()
        self.progress   = None
        self.done       = False
        self.gen_time   = 0.0
        self.stats      = {}
        self._build_cell_surf()
        pygame.display.set_caption(
            f'Map Builder — seed {self.seed}  {self.width}×{self.height}  '
            f'coast={coast}'
        )

    def _build_cell_surf(self) -> None:
        """Create (or re-create) the per-cell pixel surface."""
        self.cell_surf = pygame.Surface((self.width, self.height))
        self.cell_surf.fill(C_UNINIT)

    def _step(self) -> None:
        """Advance the generator by one yield. Returns silently when done."""
        if self.done or self.gen_iter is None:
            return
        try:
            t0              = time.perf_counter()
            self.progress   = next(self.gen_iter)
            self.gen_time  += time.perf_counter() - t0
            self._refresh_cell_surf()
            if self.progress.phase == PHASE_COMPLETE:
                self.done  = True
                self.stats = self.generator.stats
        except StopIteration:
            self.done = True

    def _refresh_cell_surf(self) -> None:
        """Redraw every cell onto the small cell surface (1 px per cell)."""
        if self.generator is None:
            return
        grid   = self.generator.grid
        width  = self.width
        height = self.height
        pix    = pygame.PixelArray(self.cell_surf)
        for r in range(height):
            for c in range(width):
                cell = grid[r][c]

                # Task 2: shadow suggestion — south/east lot edge = slightly darker
                shadow = 0.0
                if cell.lot_id >= 0:
                    if r + 1 < height and grid[r + 1][c].lot_id != cell.lot_id:
                        shadow += 0.18
                    if c + 1 < width and grid[r][c + 1].lot_id != cell.lot_id:
                        shadow += 0.12

                color = cell_color(cell, r, c, grid)
                if shadow > 0.0:
                    color = tuple(max(10, int(ch * (1.0 - shadow))) for ch in color)
                pix[c, r] = self.cell_surf.map_rgb(*color)
        del pix

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _compute_view(self) -> tuple[int, int, int, int, int, int]:
        """Return (cell_w, cell_h, scaled_w, scaled_h, ox, oy) for current zoom."""
        base_cw = WIN_W  / self.width
        base_ch = GRID_H / self.height
        base_cs = min(base_cw, base_ch)         # fit-to-window cell size
        cell_sz  = max(2, int(base_cs * self.zoom))
        scaled_w = cell_sz * self.width
        scaled_h = cell_sz * self.height
        # Centre without pan, then apply pan
        ox = (WIN_W  - scaled_w) // 2 + self.pan_x
        oy = (GRID_H - scaled_h) // 2 + self.pan_y
        return cell_sz, cell_sz, scaled_w, scaled_h, ox, oy

    def _draw_grid(self) -> None:
        cell_sz, _, sw, sh, ox, oy = self._compute_view()
        if self.cell_surf is None:
            return

        # Task 13: smooth scaling at higher zoom levels for softer appearance
        if self.zoom >= 2.0:
            scaled = pygame.transform.smoothscale(self.cell_surf, (sw, sh))
        else:
            scaled = pygame.transform.scale(self.cell_surf, (sw, sh))
        self.screen.blit(scaled, (ox, oy))

        if cell_sz < 3:
            return

        grid = self.generator.grid if self.generator else None

        # ── Lot / building boundary lines ──────────────────────────────────
        if grid and cell_sz >= 3:
            C_EDGE = (15, 15, 20)
            for r in range(self.height):
                for c in range(self.width):
                    cell   = grid[r][c]
                    lot_id = getattr(cell, 'lot_id', -1)
                    is_bldg = lot_id >= 0

                    if c + 1 < self.width:
                        right = grid[r][c + 1]
                        if is_bldg and getattr(right, 'lot_id', -1) != lot_id:
                            px = ox + (c + 1) * cell_sz
                            pygame.draw.line(
                                self.screen, C_EDGE,
                                (px, oy + r * cell_sz),
                                (px, oy + (r + 1) * cell_sz - 1),
                            )

                    if r + 1 < self.height:
                        below = grid[r + 1][c]
                        if is_bldg and getattr(below, 'lot_id', -1) != lot_id:
                            py = oy + (r + 1) * cell_sz
                            pygame.draw.line(
                                self.screen, C_EDGE,
                                (ox + c * cell_sz, py),
                                (ox + (c + 1) * cell_sz - 1, py),
                            )

        # ── Building cell rendering — border + fill or diagonal roof cross ──
        if grid and cell_sz >= 5:
            BLDG_ROLES = {
                ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN,
                ROLE_BUILDING_RESI, ROLE_BUILDING_CIVIC,
            }
            ROOF_ROLES = {ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN}
            for r in range(self.height):
                for c in range(self.width):
                    cell = grid[r][c]
                    tr   = getattr(cell, 'tile_role', '')
                    if tr not in BLDG_ROLES:
                        continue
                    cx   = ox + c * cell_sz
                    cy   = oy + r * cell_sz
                    fill = cell_color(cell, r, c, grid)
                    if cell_sz >= 8 and tr in ROOF_ROLES:
                        # Task 10: subtle diagonal cross on flat rooftops (CBD/midtown)
                        pygame.draw.rect(self.screen, fill, (cx, cy, cell_sz, cell_sz))
                        cross_col = tuple(max(10, int(ch * 0.82)) for ch in fill)
                        pygame.draw.line(self.screen, cross_col,
                            (cx + 1, cy + 1), (cx + cell_sz - 2, cy + cell_sz - 2))
                        pygame.draw.line(self.screen, cross_col,
                            (cx + cell_sz - 2, cy + 1), (cx + 1, cy + cell_sz - 2))
                    else:
                        bord = tuple(max(10, int(ch * 0.65)) for ch in fill)
                        pygame.draw.rect(self.screen, bord, (cx, cy, cell_sz, cell_sz))
                        pygame.draw.rect(self.screen, fill, (cx+1, cy+1, cell_sz-2, cell_sz-2))

        # ── Task 11: Connector road kerb shadow adjacent to sidewalk ────────
        if grid and cell_sz >= 4:
            C_KERB = tuple(max(10, int(ch * 0.78)) for ch in C_CONNECTOR)
            for r in range(self.height):
                for c in range(self.width):
                    cell = grid[r][c]
                    if not (cell.is_road and cell.road_category == ROAD_CONNECTOR):
                        continue
                    cx = ox + c * cell_sz
                    cy = oy + r * cell_sz
                    # Check each cardinal side; if neighbour is sidewalk draw a kerb line
                    nbr_n = grid.cell(r - 1, c)
                    nbr_s = grid.cell(r + 1, c)
                    nbr_w = grid.cell(r, c - 1)
                    nbr_e = grid.cell(r, c + 1)
                    if nbr_n is not None and nbr_n.is_sidewalk:
                        pygame.draw.line(self.screen, C_KERB,
                            (cx, cy), (cx + cell_sz - 1, cy))
                    if nbr_s is not None and nbr_s.is_sidewalk:
                        pygame.draw.line(self.screen, C_KERB,
                            (cx, cy + cell_sz - 1), (cx + cell_sz - 1, cy + cell_sz - 1))
                    if nbr_w is not None and nbr_w.is_sidewalk:
                        pygame.draw.line(self.screen, C_KERB,
                            (cx, cy), (cx, cy + cell_sz - 1))
                    if nbr_e is not None and nbr_e.is_sidewalk:
                        pygame.draw.line(self.screen, C_KERB,
                            (cx + cell_sz - 1, cy), (cx + cell_sz - 1, cy + cell_sz - 1))

        # ── Task 4: Highway center-line lighter stripe ───────────────────────
        if grid and cell_sz >= 6:
            for r in range(self.height):
                for c in range(self.width):
                    cell = grid[r][c]
                    if not (cell.is_road and cell.road_category == ROAD_HIGHWAY):
                        continue
                    cx  = ox + c * cell_sz + cell_sz // 2
                    cy  = oy + r * cell_sz + cell_sz // 2
                    # Determine orientation from road bitmask
                    mask = grid.road_bitmask(r, c)
                    # Bits: N=8 E=4 S=2 W=1; horizontal if E or W connected
                    if mask & 0b0101:   # E or W bit → horizontal road
                        pygame.draw.line(self.screen, C_HW_CENTER,
                            (ox + c * cell_sz + 1, cy),
                            (ox + (c + 1) * cell_sz - 2, cy))
                    else:              # vertical (N/S) or default
                        pygame.draw.line(self.screen, C_HW_CENTER,
                            (cx, oy + r * cell_sz + 1),
                            (cx, oy + (r + 1) * cell_sz - 2))

    def _draw_hud(self) -> None:
        hud_y = GRID_H
        pygame.draw.rect(self.screen, C_HUD_BG, (0, hud_y, WIN_W, HUD_H))

        if self.progress is None:
            return

        phase   = self.progress.phase
        pct     = self.progress.progress
        message = self.progress.message

        # Phase colour for the progress bar
        bar_col = C_PHASE.get(phase, C_PROGRESS_FG)

        # ── Progress bar ──────────────────────────────────────────────────────
        BAR_X, BAR_Y = 14, hud_y + 10
        BAR_W, BAR_H = WIN_W - 28, 10
        pygame.draw.rect(self.screen, C_PROGRESS_BG, (BAR_X, BAR_Y, BAR_W, BAR_H), border_radius=4)
        filled = int(BAR_W * pct)
        if filled > 0:
            pygame.draw.rect(self.screen, bar_col, (BAR_X, BAR_Y, filled, BAR_H), border_radius=4)

        # ── Phase label ───────────────────────────────────────────────────────
        phase_label = phase.upper()
        ps = self.font_md.render(phase_label, True, bar_col)
        self.screen.blit(ps, (BAR_X, hud_y + 26))

        pct_s = self.font_sm.render(f'{pct*100:5.1f}%', True, C_HUD_DIM)
        self.screen.blit(pct_s, (BAR_X + ps.get_width() + 10, hud_y + 28))

        # ── Message ───────────────────────────────────────────────────────────
        msg_s = self.font_sm.render(message[:90], True, C_HUD_DIM)
        self.screen.blit(msg_s, (BAR_X, hud_y + 46))

        # ── Stats (shown after completion) ────────────────────────────────────
        if self.done and self.stats:
            s = self.stats
            districts = s.get('districts', [])
            dist_str = '  '.join(d['name'] for d in districts) if districts else ''
            info = (
                f"seed {s.get('seed')}  |  "
                f"{s.get('width')}×{s.get('height')}  |  "
                f"blocks {s.get('blocks','?')}  parks {s.get('parks','?')}  "
                f"lots {s.get('lots','?')}  spawns {s.get('spawns','?')}  "
                f"landmarks {s.get('landmarks','?')}  |  "
                f"{s.get('elapsed_s')} s"
            )
            ts = self.font_sm.render(info, True, C_HUD_TEXT)
            self.screen.blit(ts, (BAR_X, hud_y + 64))
            if dist_str:
                ds = self.font_sm.render(f'Districts: {dist_str}'[:100], True, C_HUD_DIM)
                self.screen.blit(ds, (BAR_X + ts.get_width() + 20, hud_y + 64))
        else:
            info = (
                f"seed {self.seed}  |  "
                f"{self.width}×{self.height}  |  "
                f"coast: {_COASTS[self.coast_idx]}"
            )
            ts = self.font_sm.render(info, True, C_HUD_DIM)
            self.screen.blit(ts, (BAR_X, hud_y + 64))

        # ── Key hints (right side) ─────────────────────────────────────────────
        hints = 'SPACE new  R redo  H coast  Z zone  +/- zoom  arrows pan  1-9 seed  Q quit'
        hs = self.font_sm.render(hints, True, C_HUD_DIM)
        self.screen.blit(hs, (WIN_W - hs.get_width() - 14, hud_y + 64))

        # ── Legend swatches ───────────────────────────────────────────────────
        swatches = [
            (C_WATER,          'water'),
            (C_HIGHWAY,        'highway'),
            (C_CONNECTOR,      'road'),
            (C_ALLEY,          'alley'),
            (C_PLAZA,          'plaza'),
            (C_SIDEWALK,       'sidewalk'),
            (C_BLDG_CBD,       'CBD'),
            (C_BLDG_MIDTOWN,   'midtown'),
            (C_BLDG_RESI,      'resi'),
            (C_BLDG_CIVIC,     'civic bldg'),
            (C_CIVIC,          'town hall'),
            (C_PARK,           'park'),
            (C_CLIFF,          'cliff'),
            (C_BEACH_SAND_W,   'beach'),
            (C_DOCK_PLANKS,    'dock'),
            (C_LAND,           'exterior'),
        ]
        lx = WIN_W - 14
        for colour, label in reversed(swatches):
            txt = self.font_sm.render(label, True, C_HUD_DIM)
            lx -= txt.get_width() + 4
            self.screen.blit(txt, (lx, hud_y + 28))
            lx -= 16
            pygame.draw.rect(self.screen, colour, (lx, hud_y + 28, 12, 12), border_radius=2)
            lx -= 10

    def _draw(self) -> None:
        self.screen.fill(C_BG)
        self._draw_grid()
        self._draw_hud()
        pygame.display.flip()

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self) -> bool:
        """Process all pending events. Returns False to quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                key = event.key

                if key in (pygame.K_q, pygame.K_ESCAPE):
                    return False

                elif key == pygame.K_SPACE:
                    self.seed += 1
                    self._start_generation()

                elif key == pygame.K_r:
                    self._start_generation()

                elif key == pygame.K_h:
                    self.coast_idx = (self.coast_idx + 1) % len(_COASTS)
                    self._start_generation()

                elif key == pygame.K_z:
                    global _zone_mode
                    _zone_mode = not _zone_mode
                    self._refresh_cell_surf()

                elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.zoom = min(self.zoom * 1.25, 8.0)

                elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.zoom = max(self.zoom / 1.25, 0.5)
                    self.pan_x = max(-200, min(200, self.pan_x))
                    self.pan_y = max(-200, min(200, self.pan_y))

                elif key == pygame.K_UP:    self.pan_y -= 20
                elif key == pygame.K_DOWN:  self.pan_y += 20
                elif key == pygame.K_LEFT:  self.pan_x -= 20
                elif key == pygame.K_RIGHT: self.pan_x += 20

                elif pygame.K_1 <= key <= pygame.K_9:
                    self.seed = key - pygame.K_0
                    self._start_generation()

            if event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    self.zoom = min(self.zoom * 1.15, 8.0)
                else:
                    self.zoom = max(self.zoom / 1.15, 0.5)

        return True

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        # Steps per frame during generation — keep it low so animation is visible.
        # The coastline yields ~8 times, highway ~3, connector ~20, sidewalk ~15.
        # At 1 step/frame we see everything animate. At 3 we see it faster.
        STEPS_PER_FRAME_GENERATING = 2
        STEPS_PER_FRAME_DONE       = 0  # idle once complete

        running = True
        while running:
            running = self._handle_events()

            # Advance generator
            if not self.done:
                for _ in range(STEPS_PER_FRAME_GENERATING):
                    self._step()
                    if self.done:
                        break

            self._draw()
            self.clock.tick(60)

        pygame.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Map Builder Visual Demo')
    p.add_argument('--seed',   type=int, default=1)
    p.add_argument('--coast',  type=str, default='random',
                   choices=_COASTS)
    p.add_argument('--width',  type=int, default=160)
    p.add_argument('--height', type=int, default=120)
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    MapApp(
        seed   = args.seed,
        coast  = args.coast,
        width  = args.width,
        height = args.height,
    ).run()
