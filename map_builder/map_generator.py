"""
map_builder/map_generator.py
─────────────────────────────
MapGenerator — the single public entry point for the entire pipeline.

Usage in game loop
──────────────────
    from map_builder import MapGenerator, MapConfig

    config = MapConfig(
        width        = 64,
        height       = 64,
        master_seed  = save_file.seed,
        coast_side   = 'west',
        coast_coverage = 0.25,
        highway_count  = 2,
        connector_density = 0.65,
    )

    generator = MapGenerator(config)

    # ── Non-blocking game-loop integration ────────────────────────────────────
    gen = generator.generate()          # returns a generator, nothing runs yet

    def on_update(dt):
        nonlocal gen
        if gen is None:
            return                      # already finished
        try:
            progress = next(gen)
            loading_screen.phase    = progress.phase
            loading_screen.bar      = progress.progress
            loading_screen.subtitle = progress.message
        except StopIteration:
            gen = None                  # exhausted → map is ready
            world.load_map(generator.grid)

    # ── Or: generate the whole map at once (e.g. for server/tool usage) ──────
    generator.generate_blocking()
    world.load_map(generator.grid)

Design contract
───────────────
• `generate()` yields GeneratorProgress named-tuples — never returns a value.
• `grid` is always accessible; cells are updated in-place as phases run.
• All randomness derives from config.master_seed — same seed = same map.
• Each phase can be run independently via `run_phase_*()` methods for testing.
"""
from __future__ import annotations
from typing import Generator, Optional

from .map_state import MapGrid, MapConfig, GeneratorProgress
from .constants import (
    PHASE_COMPLETE,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    ROAD_HIGHWAY,
    ROAD_CONNECTOR,
)


class MapGenerator:
    """
    Orchestrates all four generation phases into a single yield-based pipeline.

    Attributes:
        config  : MapConfig instance used for this generation run.
        grid    : MapGrid — the live map data.  Readable at any time during
                  generation; fully populated after the generator is exhausted.
        stats   : dict of generation statistics (populated on completion).
    """

    def __init__(self, config: MapConfig) -> None:
        self.config       = config
        self.grid         = MapGrid(config.width, config.height)
        self.stats:  dict = {}
        self.blocks: list = []   # list of sets of (row,col) — interior city blocks
        self.lots:   list = []   # list of sets of (row,col) — subdivided lots
        self.civic_anchor: tuple | None = None   # (row, col) of CBD civic centre cell

    # ── Primary interface ─────────────────────────────────────────────────────

    def generate(self) -> Generator[GeneratorProgress, None, None]:
        """
        Master pipeline generator.

        Yields GeneratorProgress at every meaningful step across all phases.
        Call next() once per game frame for smooth non-blocking generation.
        Exhausted when phase == PHASE_COMPLETE.
        """
        import time
        t_start = time.perf_counter()

        yield from self._run_phase_coastline()
        yield from self._run_phase_zones()
        yield from self._run_phase_civic_anchor()
        yield from self._run_phase_highways()
        yield from self._run_phase_connectors()
        yield from self._run_phase_sidewalks()
        yield from self._run_phase_blocks()
        yield from self._run_phase_parks()
        yield from self._run_phase_lots()

        # Non-yielding density post-pass — runs after all road phases
        self._compute_density_post_pass()

        yield from self._run_phase_buildings()

        t_end = time.perf_counter()
        park_count = sum(
            1 for b in self.blocks
            if b and self.grid[next(iter(b))[0]][next(iter(b))[1]].is_park
        )
        spawn_count = sum(1 for _, _, c in self.grid.all_cells() if c.is_spawn_point)
        # Count distinct landmark buildings: each unique (landmark_type, lot_id) pair
        # is one building; fallback counts unique landmark types if no lot_ids.
        landmark_lots: set = set()
        landmark_cells = 0
        for _, _, c in self.grid.all_cells():
            if c.landmark_type:
                landmark_cells += 1
                key = (c.landmark_type, c.lot_id) if c.lot_id >= 0 else (c.landmark_type, id(c))
                landmark_lots.add(key)
        # Distinct landmark buildings = unique (type, lot_id) pairs
        landmark_count = len(set(k[0] for k in landmark_lots))  # unique types placed
        self.stats = {
            'seed':      self.config.master_seed,
            'width':     self.config.width,
            'height':    self.config.height,
            'land':      self.grid.land_count(),
            'water':     self.grid.water_count(),
            'roads':     self.grid.road_count(),
            'sidewalks': self.grid.sidewalk_count(),
            'blocks':    len(self.blocks),
            'parks':     park_count,
            'lots':      len(self.lots),
            'spawns':    spawn_count,
            'landmarks': landmark_count,
            'elapsed_s': round(t_end - t_start, 3),
            'zones':     self.grid.zone_count(),
        }

        yield GeneratorProgress(
            PHASE_COMPLETE,
            1.0,
            (
                f"Map ready — {self.stats['land']} land / "
                f"{self.stats['water']} water / "
                f"{self.stats['roads']} road / "
                f"{self.stats['sidewalks']} sidewalk  |  "
                f"{self.stats['blocks']} blocks  {self.stats['parks']} parks  "
                f"{self.stats['lots']} lots  {self.stats['spawns']} spawns  "
                f"in {self.stats['elapsed_s']}s"
            ),
        )

    def generate_blocking(self) -> None:
        """
        Consume the generator to completion in one call.
        Use for server-side generation, unit tests, or command-line tools.
        Does not tick a loading screen.
        """
        for _ in self.generate():
            pass

    # ── Per-phase runners (useful for isolated testing) ───────────────────────

    def _run_phase_coastline(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.coastline import generate_coastline
        yield from generate_coastline(self.grid, self.config)

    def _run_phase_zones(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.zones import generate_zones
        yield from generate_zones(self.grid, self.config)

    def _run_phase_highways(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.highway import generate_highways
        yield from generate_highways(self.grid, self.config)

    def _run_phase_connectors(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.connector import generate_connectors
        yield from generate_connectors(self.grid, self.config)

    def _run_phase_sidewalks(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.sidewalk import generate_sidewalks
        yield from generate_sidewalks(self.grid, self.config)

    def _run_phase_civic_anchor(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.civic import generate_civic_anchor
        anchor_sink: list = []
        yield from generate_civic_anchor(self.grid, self.config, sink=anchor_sink)
        if anchor_sink:
            self.civic_anchor = anchor_sink[0]

    def _run_phase_blocks(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.blocks import generate_blocks
        self.blocks = []
        yield from generate_blocks(self.grid, self.config, sink=self.blocks)

    def _run_phase_parks(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.parks import generate_parks
        yield from generate_parks(self.grid, self.config, self.blocks)

    def _run_phase_lots(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.lots import generate_lots
        self.lots = []
        yield from generate_lots(self.grid, self.config, self.blocks, sink=self.lots)

    def _run_phase_buildings(self) -> Generator[GeneratorProgress, None, None]:
        from .phases.buildings import generate_buildings
        yield from generate_buildings(
            self.grid, self.config, self.blocks, self.lots, self.civic_anchor
        )

    def _compute_density_post_pass(self) -> None:
        """
        O(N) BFS multi-source density score computation (replaces O(N×HW) loop).
        Runs after all road phases so highway cells are fully placed.
        Sets cell.density_score on every land cell.

        Algorithm: BFS from all highway cells simultaneously builds a Chebyshev
        distance field in O(width × height). Each land cell then reads its
        pre-computed distance in O(1).
        """
        from collections import deque

        rows, cols = self.grid.height, self.grid.width
        zone_base = {ZONE_CBD: 0.85, ZONE_MIDTOWN: 0.55, ZONE_RESIDENTIAL: 0.25}

        # ── Build BFS distance field from all highway cells ───────────────────
        INF = 999
        dist_grid = [[INF] * cols for _ in range(rows)]
        queue: deque = deque()

        for r, c, cell in self.grid.all_cells():
            if cell.is_road and cell.road_category == ROAD_HIGHWAY:
                dist_grid[r][c] = 0
                queue.append((r, c, 0))

        # 4-directional BFS — Chebyshev equivalent via ∞-norm with 4-connectivity
        # gives Manhattan distance, which is a good proxy for Chebyshev here.
        while queue:
            r, c, d = queue.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and dist_grid[nr][nc] > d + 1:
                    dist_grid[nr][nc] = d + 1
                    queue.append((nr, nc, d + 1))

        # ── Assign density_score to all land cells ────────────────────────────
        for r, c, cell in self.grid.all_cells():
            if not cell.is_land:
                continue
            base = zone_base.get(cell.zone_id, 0.25)
            min_dist = dist_grid[r][c] if dist_grid[r][c] < INF else 20
            hw_bonus = max(0.0, 0.15 * (1.0 - min(min_dist, 10) / 10.0))
            cell.density_score = min(1.0, max(0.0, base + hw_bonus))

    # ── Serialisation stubs (wired to your save system) ───────────────────────

    def to_dict(self) -> dict:
        """
        Serialise the generated map to a plain dict.
        Store this in your save file alongside config.master_seed.
        On reload, pass master_seed back to MapConfig and regenerate —
        deterministic output means you never need to save the full grid.
        """
        return {
            'seed':   self.config.master_seed,
            'width':  self.config.width,
            'height': self.config.height,
            'config': {
                'coast_side':              self.config.coast_side,
                'coast_coverage':          self.config.coast_coverage,
                'coast_noise_scale':       self.config.coast_noise_scale,
                'coast_smoothing_passes':  self.config.coast_smoothing_passes,
                'highway_ns_min':          self.config.highway_ns_min,
                'highway_ns_max':          self.config.highway_ns_max,
                'highway_ew_min':          self.config.highway_ew_min,
                'highway_ew_max':          self.config.highway_ew_max,
                'highway_organic':         self.config.highway_organic,
                'connector_density':       self.config.connector_density,
                'connector_spacing':       self.config.connector_spacing,
                'avenue_spacing':          self.config.avenue_spacing,
                'min_block_depth':         self.config.min_block_depth,
                'connector_max_length':    self.config.connector_max_length,
                'connector_turn_bias':     self.config.connector_turn_bias,
                'roundabout_count':        self.config.roundabout_count,
                'diagonal_streets':        self.config.diagonal_streets,
                'sidewalk_depth':          self.config.sidewalk_depth,
                'sidewalk_damage_rate':    self.config.sidewalk_damage_rate,
            },
            'stats': self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MapGenerator':
        """
        Reconstruct a MapGenerator from a saved dict.
        Call generate_blocking() to reproduce the map identically.
        """
        cfg_data = data.get('config', {})
        config = MapConfig(
            width                  = data['width'],
            height                 = data['height'],
            master_seed            = data['seed'],
            coast_side             = cfg_data.get('coast_side',             'none'),
            coast_coverage         = cfg_data.get('coast_coverage',         0.30),
            coast_noise_scale      = cfg_data.get('coast_noise_scale',      3.5),
            coast_smoothing_passes = cfg_data.get('coast_smoothing_passes', 2),
            highway_ns_min         = cfg_data.get('highway_ns_min',         2),
            highway_ns_max         = cfg_data.get('highway_ns_max',         5),
            highway_ew_min         = cfg_data.get('highway_ew_min',         0),
            highway_ew_max         = cfg_data.get('highway_ew_max',         3),
            highway_organic        = cfg_data.get('highway_organic',        0.3),
            connector_density      = cfg_data.get('connector_density',      0.70),
            connector_spacing      = cfg_data.get('connector_spacing',      8),
            avenue_spacing         = cfg_data.get('avenue_spacing',         27),
            min_block_depth        = cfg_data.get('min_block_depth',        3),
            connector_max_length   = cfg_data.get('connector_max_length',   20),
            connector_turn_bias    = cfg_data.get('connector_turn_bias',    0.05),
            roundabout_count       = cfg_data.get('roundabout_count',       3),
            diagonal_streets       = cfg_data.get('diagonal_streets',       1),
            sidewalk_depth         = cfg_data.get('sidewalk_depth',         1),
            sidewalk_damage_rate   = cfg_data.get('sidewalk_damage_rate',   0.15),
        )
        return cls(config)
