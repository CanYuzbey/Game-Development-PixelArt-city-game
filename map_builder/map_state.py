"""
map_builder/map_state.py
─────────────────────────
Core data structures: MapCell, MapGrid, GeneratorProgress, MapConfig.

These are the only objects the game engine needs to import.
The generator fills a MapGrid; the renderer reads it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Generator, NamedTuple

from .constants import (
    LAYER_GROUND, LAYER_ROAD, LAYER_SIDEWALK, LAYER_DECOR,
    COAST_NONE, COAST_RANDOM,
    ROAD_CONNECTOR,
    ZONE_CBD,
)


# ── MapCell ───────────────────────────────────────────────────────────────────

@dataclass
class MapCell:
    """
    One tile in the world grid.

    layers      : dict[int → tile_id str or None]
                  Keys are LAYER_* constants.  None = empty layer.
    is_water    : True if this cell is ocean/river — impassable, no roads.
    is_land     : True if this cell is dry ground (can receive road/sidewalk).
    road_category : ROAD_HIGHWAY | ROAD_CONNECTOR | None
    variation   : variation index into TileRegistry.get_variants() — lets the
                  renderer pick the same random variant every frame without
                  re-rolling.
    """
    layers:        dict = field(default_factory=lambda: {
        LAYER_GROUND:   None,
        LAYER_ROAD:     None,
        LAYER_SIDEWALK: None,
        LAYER_DECOR:    None,
    })
    is_water:      bool = False
    is_land:       bool = False
    road_category: Optional[str] = None
    zone_id:       int  = ZONE_CBD   # default = 0 (CBD); updated by zones phase
    variation:     dict = field(default_factory=lambda: {
        LAYER_GROUND:   0,
        LAYER_ROAD:     0,
        LAYER_SIDEWALK: 0,
        LAYER_DECOR:    0,
    })

    # ── Convenience accessors ─────────────────────────────────────────────────

    @property
    def is_road(self) -> bool:
        return self.layers[LAYER_ROAD] is not None

    @property
    def is_sidewalk(self) -> bool:
        return self.layers[LAYER_SIDEWALK] is not None

    def set_road(self, tile_id: str, category: str, variation: int = 0) -> None:
        self.layers[LAYER_ROAD] = tile_id
        self.road_category      = category
        self.variation[LAYER_ROAD] = variation

    def set_sidewalk(self, tile_id: str, variation: int = 0) -> None:
        self.layers[LAYER_SIDEWALK] = tile_id
        self.variation[LAYER_SIDEWALK] = variation

    def set_ground(self, tile_id: str, variation: int = 0) -> None:
        self.layers[LAYER_GROUND] = tile_id
        self.variation[LAYER_GROUND] = variation

    def set_decor(self, tile_id: str, variation: int = 0) -> None:
        self.layers[LAYER_DECOR] = tile_id
        self.variation[LAYER_DECOR] = variation

    def clear_road(self) -> None:
        self.layers[LAYER_ROAD] = None
        self.road_category = None

    def __repr__(self) -> str:
        flags = []
        if self.is_water: flags.append('W')
        if self.is_road:  flags.append(f'R({self.road_category[0].upper()})')
        if self.is_sidewalk: flags.append('S')
        return f'Cell[{"".join(flags) or "land"}]'


# ── MapGrid ───────────────────────────────────────────────────────────────────

class MapGrid:
    """
    2-D grid of MapCell objects indexed by (row, col).

    Designed for direct use in a game engine:
      • grid[row][col]  or  grid.cell(row, col) for safe access
      • grid.in_bounds(row, col)  before indexing with arbitrary coords
      • Iterable row-by-row via  for row in grid.rows()
    """

    def __init__(self, width: int, height: int) -> None:
        self.width  = width
        self.height = height
        self._cells: list[list[MapCell]] = [
            [MapCell() for _ in range(width)]
            for _ in range(height)
        ]

    # ── Access ────────────────────────────────────────────────────────────────

    def __getitem__(self, row: int) -> list[MapCell]:
        return self._cells[row]

    def cell(self, row: int, col: int) -> Optional[MapCell]:
        """Return cell or None if out of bounds — safe to call without guard."""
        if self.in_bounds(row, col):
            return self._cells[row][col]
        return None

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def rows(self):
        """Iterate over all rows (each row is a list[MapCell])."""
        return iter(self._cells)

    def all_cells(self):
        """Yield (row, col, MapCell) for every cell in the grid."""
        for r, row in enumerate(self._cells):
            for c, cell in enumerate(row):
                yield r, c, cell

    # ── Neighbour helpers ─────────────────────────────────────────────────────

    def neighbours(self, row: int, col: int) -> dict[int, Optional[MapCell]]:
        """
        Return dict of {direction: MapCell or None} for the 4 cardinal neighbours.
        Uses direction constants N=0, E=1, S=2, W=3.
        """
        from .constants import DIRECTION_OFFSETS
        return {
            d: self.cell(row + dr, col + dc)
            for d, (dr, dc) in DIRECTION_OFFSETS.items()
        }

    def road_bitmask(self, row: int, col: int) -> int:
        """
        Compute 4-bit road-connectivity bitmask for cell (row, col).
        Bit set = that neighbour is also a road cell.
        N=8  E=4  S=2  W=1
        """
        from .constants import DIR_BIT, DIRECTION_OFFSETS
        mask = 0
        for d, (dr, dc) in DIRECTION_OFFSETS.items():
            nbr = self.cell(row + dr, col + dc)
            if nbr is not None and nbr.is_road:
                mask |= DIR_BIT[d]
        return mask

    def road_adjacency_bitmask(self, row: int, col: int) -> int:
        """
        Compute 4-bit bitmask of which neighbours of (row,col) are CONNECTOR roads.
        Used by the sidewalk phase to pick the correct sidewalk tile.
        """
        from .constants import DIR_BIT, DIRECTION_OFFSETS, ROAD_CONNECTOR
        mask = 0
        for d, (dr, dc) in DIRECTION_OFFSETS.items():
            nbr = self.cell(row + dr, col + dc)
            if nbr is not None and nbr.is_road and nbr.road_category == ROAD_CONNECTOR:
                mask |= DIR_BIT[d]
        return mask

    # ── Stats ─────────────────────────────────────────────────────────────────

    def land_count(self) -> int:
        return sum(1 for _, _, c in self.all_cells() if c.is_land)

    def water_count(self) -> int:
        return sum(1 for _, _, c in self.all_cells() if c.is_water)

    def road_count(self) -> int:
        return sum(1 for _, _, c in self.all_cells() if c.is_road)

    def sidewalk_count(self) -> int:
        return sum(1 for _, _, c in self.all_cells() if c.is_sidewalk)

    def zone_count(self) -> dict:
        """Return {zone_id: cell_count} for all land cells."""
        counts: dict[int, int] = {}
        for row in self._cells:
            for cell in row:
                if cell.is_land:
                    counts[cell.zone_id] = counts.get(cell.zone_id, 0) + 1
        return counts


# ── GeneratorProgress ─────────────────────────────────────────────────────────

class GeneratorProgress(NamedTuple):
    """
    Yielded by MapGenerator.generate() at each step.

    Consume in your game loop:
        gen = MapGenerator(config).generate()
        for progress in gen:
            loading_bar.set(progress.progress)
            status_label.set(progress.message)
        # loop exhausted → map complete, read generator.grid

    Fields:
        phase    : PHASE_* constant string
        progress : float 0.0–1.0 within the current phase
        message  : human-readable status string (for loading screens)
    """
    phase:    str
    progress: float
    message:  str


# ── MapConfig ─────────────────────────────────────────────────────────────────

@dataclass
class MapConfig:
    """
    All generation parameters for one map.

    One master_seed controls all four phases deterministically.
    The same seed always produces the identical map.
    """
    # ── Size ──────────────────────────────────────────────────────────────────
    width:  int = 96    # grid columns  (~960m at 10m/cell)
    height: int = 72    # grid rows     (~720m at 10m/cell)

    # ── Seed ──────────────────────────────────────────────────────────────────
    master_seed: int = 1

    # ── Phase 1 — Coastline ───────────────────────────────────────────────────
    coast_side:      str   = COAST_NONE  # 'none'|'north'|'south'|'east'|'west'|'random'
    coast_coverage:  float = 0.28        # fraction of map that is water (0–0.6)
    coast_noise_scale: float = 3.5       # lower = smoother coast; higher = jagged
    coast_smoothing_passes: int = 2      # erosion passes after thresholding

    # ── Phase 2 — Highways (separate Y-axis / X-axis counts) ─────────────────
    # Actual count is drawn each generation from triangular(min, max, mode=min),
    # so most maps produce the minimum while rare seeds push toward the maximum.
    highway_ns_min:  int   = 2           # N-S (Y-axis) highway count — mode / min
    highway_ns_max:  int   = 5           # N-S highway count — ceiling
    highway_ew_min:  int   = 0           # E-W (X-axis) highway count — mode / min
    highway_ew_max:  int   = 3           # E-W highway count — ceiling
    highway_organic: float = 0.3         # organic deviation 0=perfectly straight

    # ── Phase 3 — Connectors (dense city grid) ───────────────────────────────
    # Block geometry at 10m/cell:
    #   avenue_spacing=24  →  240m N-S corridor  (medium US city grid)
    #   connector_spacing=12 →  120m E-W block
    #   ratio 2.0:1 — moderate urban proportions (~35–40% road density target)
    connector_density:    float = 0.70   # 0=sparse 1=dense
    connector_spacing:    int   = 12     # E-W cross-street row spacing (cells)
    avenue_spacing:       int   = 24     # N-S avenue column spacing (cells)
    min_block_depth:      int   = 2      # guaranteed clear cells between parallel roads
    connector_max_length: int   = 20     # legacy, unused by grid algorithm
    connector_turn_bias:  float = 0.05   # Perlin drift amplitude (0=dead-straight)
    roundabout_count:     int   = 10     # max circle junctions
    diagonal_streets:     int   = 2      # Broadway / Diagonal Ave style diagonals

    # ── Phase 4 — Sidewalks ───────────────────────────────────────────────────
    sidewalk_depth:      int   = 1       # cells of sidewalk on each side of road
    sidewalk_damage_rate: float = 0.15   # probability a sidewalk tile is damaged variant

    def __post_init__(self) -> None:
        assert 16 <= self.width  <= 256, "width must be 16–256"
        assert 16 <= self.height <= 256, "height must be 16–256"
        assert 0.0 <= self.coast_coverage <= 0.65
        assert 0.0 <= self.connector_density <= 1.0
        assert self.highway_ns_min >= 0
        assert self.highway_ns_max >= self.highway_ns_min
        assert self.highway_ew_min >= 0
        assert self.highway_ew_max >= self.highway_ew_min
        assert self.connector_spacing >= 2
        assert self.avenue_spacing >= self.connector_spacing
        assert self.min_block_depth >= 1
        assert self.roundabout_count >= 0
        assert self.diagonal_streets >= 0
