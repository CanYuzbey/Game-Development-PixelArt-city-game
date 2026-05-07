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
"""
from __future__ import annotations
import sys, io, time, argparse

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pygame

from map_builder             import MapGenerator, MapConfig, PHASE_COMPLETE
from map_builder.constants   import (
    LAYER_DECOR,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    PHASE_COASTLINE, PHASE_HIGHWAY, PHASE_CONNECTOR,
    PHASE_SIDEWALK,
)


# ── Colour palette ─────────────────────────────────────────────────────────────

C_BG          = ( 18,  18,  22)   # window background (near-black)
C_UNINIT      = ( 30,  30,  38)   # un-generated cell
C_WATER       = ( 38,  92, 180)   # ocean / river
C_LAND        = (112,  97,  72)   # dry earth (warm brown)
C_HIGHWAY     = (240, 195,  50)   # highway (gold)
C_CONNECTOR   = ( 55, 195, 220)   # connector road (cyan)
C_SIDEWALK    = (155, 152, 142)   # concrete sidewalk
C_GRID        = ( 28,  28,  35)   # inter-cell grid line
C_HUD_BG      = ( 14,  14,  20)   # HUD background strip
C_HUD_TEXT    = (215, 215, 215)   # primary HUD text
C_HUD_DIM     = (110, 110, 120)   # secondary / dim HUD text
C_PROGRESS_BG = ( 38,  38,  48)   # progress bar background
C_PROGRESS_FG = ( 60, 185, 115)   # progress bar fill (green)

# Phase accent colours for the progress bar
C_PHASE = {
    PHASE_COASTLINE:  ( 38, 120, 210),
    PHASE_HIGHWAY:    (235, 185,  45),
    PHASE_CONNECTOR:  ( 55, 195, 220),
    PHASE_SIDEWALK:   (155, 152, 142),
    PHASE_COMPLETE:   ( 60, 185, 115),
}

# Coast cycle list (for H key)
_COASTS = ['none', 'north', 'south', 'east', 'west', 'random']

# ── Layout constants ───────────────────────────────────────────────────────────

WIN_W  = 1100
WIN_H  = 740
HUD_H  = 90          # pixels reserved for the bottom HUD strip
GRID_H = WIN_H - HUD_H


# ── Helpers ────────────────────────────────────────────────────────────────────

def cell_color(cell) -> tuple[int, int, int]:
    """Return the display colour for one MapCell."""
    if cell.is_water:
        return C_WATER
    if cell.is_road:
        if cell.road_category == ROAD_HIGHWAY:
            return C_HIGHWAY
        # Marked junctions (crosswalk / yield) render slightly brighter
        if cell.layers.get(LAYER_DECOR) is not None:
            return (90, 215, 240)
        return C_CONNECTOR
    if cell.is_sidewalk:
        return C_SIDEWALK
    if cell.is_land:
        return C_LAND
    return C_UNINIT



def build_config(seed: int, coast: str, width: int, height: int) -> MapConfig:
    return MapConfig(
        width              = width,
        height             = height,
        master_seed        = seed,
        coast_side         = coast,
        coast_coverage     = 0.30,
        # Highways — yellow, tie city to other lands; kept sparse
        highway_ns_min     = 2,
        highway_ns_max     = 4,
        highway_ew_min     = 0,
        highway_ew_max     = 2,
        highway_organic    = 0.25,
        # Connector grid — blue main city roads, dense urban proportions at 10m/cell
        #   avenue_spacing=15  → 150m N-S corridor  (tight EU/city-centre grid)
        #   connector_spacing=6 →  60m E-W block
        #   ratio 2.5:1
        connector_density  = 0.85,
        connector_spacing  = 6,    # E-W cross-streets every ~60m
        avenue_spacing     = 15,   # N-S avenues every ~150m
        min_block_depth    = 2,
        connector_turn_bias  = 0.05,
        roundabout_count     = 15,
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
        pix = pygame.PixelArray(self.cell_surf)
        for r, row in enumerate(self.generator.grid.rows()):
            for c, cell in enumerate(row):
                pix[c, r] = self.cell_surf.map_rgb(*cell_color(cell))
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
        # Scale the cell surface up to display size
        scaled = pygame.transform.scale(self.cell_surf, (sw, sh))
        self.screen.blit(scaled, (ox, oy))

        # Draw grid lines only when large enough to be useful
        if cell_sz >= 6:
            for c in range(self.width + 1):
                x = ox + c * cell_sz
                pygame.draw.line(self.screen, C_GRID, (x, oy), (x, oy + sh))
            for r in range(self.height + 1):
                y = oy + r * cell_sz
                pygame.draw.line(self.screen, C_GRID, (ox, y), (ox + sw, y))

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
            info = (
                f"seed {s.get('seed')}  |  "
                f"{s.get('width')}×{s.get('height')}  |  "
                f"land {s.get('land')}  water {s.get('water')}  "
                f"roads {s.get('roads')}  sidewalks {s.get('sidewalks')}  |  "
                f"{s.get('elapsed_s')} s"
            )
            ts = self.font_sm.render(info, True, C_HUD_TEXT)
            self.screen.blit(ts, (BAR_X, hud_y + 64))
        else:
            info = (
                f"seed {self.seed}  |  "
                f"{self.width}×{self.height}  |  "
                f"coast: {_COASTS[self.coast_idx]}"
            )
            ts = self.font_sm.render(info, True, C_HUD_DIM)
            self.screen.blit(ts, (BAR_X, hud_y + 64))

        # ── Key hints (right side) ─────────────────────────────────────────────
        hints = 'SPACE new  R redo  H coast  +/- zoom  arrows pan  1-9 seed  Q quit'
        hs = self.font_sm.render(hints, True, C_HUD_DIM)
        self.screen.blit(hs, (WIN_W - hs.get_width() - 14, hud_y + 64))

        # ── Legend swatches ───────────────────────────────────────────────────
        swatches = [
            (C_WATER,          'water'),
            (C_LAND,           'land'),
            (C_HIGHWAY,        'highway'),
            (C_CONNECTOR,      'road'),
            ((90, 215, 240),   'junction'),
            (C_SIDEWALK,       'sidewalk'),
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
