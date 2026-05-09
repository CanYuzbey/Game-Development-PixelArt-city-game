"""
main.py
────────
Demo runner for the Map Builder engine.

Run:    python main.py
        python main.py --seed 42 --coast west --width 48 --height 32

The ASCII renderer lets you verify the algorithm without any game engine.

Legend:
  ~  water          .  bare land
  H  highway        C  connector road
  s  sidewalk       #  road + sidewalk
"""
from __future__ import annotations
import sys
import io
import time
import argparse

# Force UTF-8 output on Windows so box-drawing and block chars render correctly
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from map_builder             import MapGenerator, MapConfig, PHASE_COMPLETE
from map_builder.constants   import (
    LAYER_ROAD, LAYER_SIDEWALK,
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    COAST_NONE,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
)


# ── ASCII renderer ────────────────────────────────────────────────────────────

_ROAD_GLYPH = {
    # bitmask 4-char key → display char
    'road_0000': '▪', 'road_0001': '╴', 'road_0010': '╷',
    'road_0011': '┘', 'road_0100': '╶', 'road_0101': '─',
    'road_0110': '└', 'road_0111': '┴', 'road_1000': '╵',
    'road_1001': '┐', 'road_1010': '│', 'road_1011': '┤',
    'road_1100': '┌', 'road_1101': '┬', 'road_1110': '├',
    'road_1111': '┼',
}

# Highway versions use the same shapes, different colour in terminal
_HW_GLYPH = {k: v for k, v in _ROAD_GLYPH.items()}


_TILE_ROLE_GLYPH = {
    # RPG tile roles → (ansi_code, char) — shown in non-zone mode too
    'park':      ('\033[0;32m', 'p'),    # green p
    'alley':     ('\033[0;35m', 'a'),    # magenta a
    'plaza':     ('\033[1;32m', '◉'),    # bright green roundabout
    'bldg_cbd':  ('\033[0;90m', '█'),    # dark gray block
    'bldg_mid':  ('\033[0;33m', '▓'),    # yellow-ish block
    'bldg_resi': ('\033[0;37m', '░'),    # light block
    'bldg_civic':('\033[1;36m', '▣'),    # bright cyan
}


def render_ascii(grid, zone_mode: bool = False) -> str:
    lines: list[str] = []
    for row in grid.rows():
        line: list[str] = []
        for cell in row:
            if cell.is_water:
                line.append('~')
                continue

            # ── Roads ─────────────────────────────────────────────────────────
            if cell.is_road:
                tid  = cell.layers[LAYER_ROAD] or 'road_1010'
                if tid.startswith('roundabout_'):
                    line.append('\033[1;32m◉\033[0m')
                    continue
                tile_role = getattr(cell, 'tile_role', '')
                base  = tid.replace('_hw', '')
                glyph = _ROAD_GLYPH.get(base, '?')
                if tile_role == 'alley':
                    line.append(f'\033[0;35m{glyph}\033[0m')
                elif cell.road_category == ROAD_HIGHWAY:
                    line.append(f'\033[1;33m{glyph}\033[0m')
                else:
                    line.append(f'\033[0;36m{glyph}\033[0m')
                continue

            # ── Land ──────────────────────────────────────────────────────────
            if cell.is_land:
                tile_role = getattr(cell, 'tile_role', '')
                lm_type   = getattr(cell, 'landmark_type', '')

                # Landmark buildings (cyan ▣) — overrides building type
                if lm_type and not getattr(cell, 'is_civic_anchor', False):
                    line.append('\033[1;36m▣\033[0m')
                    continue

                # Civic anchor
                if getattr(cell, 'is_civic_anchor', False):
                    line.append('\033[1;31m★\033[0m')
                    continue

                # Park — always green (before sidewalk check)
                if getattr(cell, 'is_park', False):
                    line.append('\033[0;32mp\033[0m')
                    continue

                # RPG tile role glyph (buildings, alleys, plazas)
                if tile_role in _TILE_ROLE_GLYPH:
                    ansi, ch = _TILE_ROLE_GLYPH[tile_role]
                    line.append(f'{ansi}{ch}\033[0m')
                    continue

                # Sidewalk
                if cell.is_sidewalk:
                    line.append('\033[0;37ms\033[0m')
                    continue

                # Bare exterior land
                if zone_mode:
                    if cell.zone_id == ZONE_CBD:
                        line.append('\033[0;33m·\033[0m')
                    elif cell.zone_id == ZONE_MIDTOWN:
                        line.append('\033[0;32m,\033[0m')
                    else:
                        line.append('.')
                else:
                    line.append('.')
                continue

            # ── Fallback ──────────────────────────────────────────────────────
            line.append(' ')
        lines.append(''.join(line))
    return '\n'.join(lines)


def print_stats(gen: MapGenerator) -> None:
    s = gen.stats
    print()
    print('─' * 50)
    print(f"  Seed       {s.get('seed')}")
    print(f"  Size       {s.get('width')} × {s.get('height')}")
    print(f"  Land       {s.get('land')} cells")
    print(f"  Water      {s.get('water')} cells")
    print(f"  Roads      {s.get('roads')} cells")
    print(f"  Sidewalks  {s.get('sidewalks')} cells")
    if s.get('blocks') is not None:
        print(f"  Blocks     {s.get('blocks')}")
        print(f"  Parks      {s.get('parks')}")
        print(f"  Lots       {s.get('lots')}")
        print(f"  Spawns     {s.get('spawns', '?')}")
        print(f"  Landmarks  {s.get('landmarks', '?')}")
    print(f"  Time       {s.get('elapsed_s')} s")
    print('─' * 50)


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Map Builder demo')
    p.add_argument('--seed',      type=int,   default=1,     help='Master seed')
    p.add_argument('--coast',     type=str,   default='random',
                   choices=['none', 'north', 'south', 'east', 'west', 'random'])
    p.add_argument('--coverage',  type=float, default=0.30,  help='Water coverage 0–0.6')
    p.add_argument('--width',     type=int,   default=160)
    p.add_argument('--height',    type=int,   default=120)
    p.add_argument('--hw-ns-max', type=int,   default=5,     help='N-S highway max count')
    p.add_argument('--hw-ew-max', type=int,   default=3,     help='E-W highway max count')
    p.add_argument('--density',   type=float, default=0.85,  help='Connector density 0–1')
    p.add_argument('--quiet',     action='store_true',       help='Suppress phase messages')
    p.add_argument('--no-render', action='store_true',       help='Skip ASCII render')
    p.add_argument('--zones',     action='store_true',       help='Show zone overlay in ASCII render')
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    config = MapConfig(
        width              = args.width,
        height             = args.height,
        master_seed        = args.seed,
        coast_side         = args.coast,
        coast_coverage     = min(0.28, args.coverage),   # cap at 0.28 for city density
        highway_ns_min     = 2,
        highway_ns_max     = getattr(args, 'hw_ns_max', 4),
        highway_ew_min     = 0,
        highway_ew_max     = getattr(args, 'hw_ew_max', 2),
        connector_density  = args.density,
        connector_spacing  = 8,    # Sprint 3: 80m E-W block depth (EU/Asian city scale)
        avenue_spacing     = 18,   # Sprint 3: 180m N-S corridor — realistic dense urban
        min_block_depth    = 2,
        connector_turn_bias  = 0.08,   # slightly more organic streets
        roundabout_count     = 8,      # fewer roundabouts for cleaner grid feel
        diagonal_streets     = 2,
        sidewalk_damage_rate = 0.15,
    )

    print(f'\n  Map Builder Engine  —  seed {args.seed}  {args.width}×{args.height}')
    print(f'  Coast: {args.coast}  coverage: {args.coverage}  '
          f'N-S hw max: {config.highway_ns_max}  E-W hw max: {config.highway_ew_max}  '
          f'density: {args.density}')
    print()

    generator = MapGenerator(config)
    gen       = generator.generate()

    last_phase = ''
    for progress in gen:
        if progress.phase != last_phase:
            last_phase = progress.phase
            print(f'  [{progress.phase.upper():12s}]', end=' ', flush=True)
        if not args.quiet:
            bar_len  = 20
            filled   = int(progress.progress * bar_len)
            bar      = '█' * filled + '░' * (bar_len - filled)
            print(f'\r  [{progress.phase.upper():12s}] [{bar}] {progress.progress*100:5.1f}%  {progress.message[:70]:70s}',
                  end='', flush=True)
        if progress.phase == PHASE_COMPLETE:
            print()

    print_stats(generator)

    if not args.no_render:
        print()
        print(render_ascii(generator.grid, zone_mode=args.zones))
        print()
        legend = ('Legend:  ~ water   . land   \033[1;33m━ highway\033[0m   '
                  '\033[0;36m┼ connector\033[0m   \033[0;37ms sidewalk\033[0m   '
                  '\033[1;32m◉ roundabout\033[0m')
        if args.zones:
            legend += ('   \033[0;33m· CBD\033[0m   \033[0;32m, Midtown\033[0m   '
                       '. Residential   \033[0;32mp park\033[0m   \033[1;31m★ civic\033[0m')
        print(legend)
        print()


if __name__ == '__main__':
    main()
