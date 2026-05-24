"""
map_builder/phases/elevation.py
─────────────────────────────────
Sprint 5 — Elevation Layer

Generates a smooth terrain-height field stored as cell.elevation (0.0–1.0).
Uses low-frequency FBM noise (1 cycle per ~50 cells) to simulate gentle
topography: higher ground near the city centre, lower near the coast.

Design constraints:
  • Elevation is purely visual — roads ignore it (simplification).
  • Water cells always have elevation = 0.0 (sea level).
  • Land cells get elevation 0.0–1.0 from a seeded FBM pass.
  • Very low frequency: scale = (1.0 / 50 cells) so the whole map
    shows at most 1–2 gentle hills.

App.py uses elevation for a subtle brightness shift:
  +8 brightness at elevation > 0.65 (hilltop, warmer/lighter)
  -6 brightness at elevation < 0.35 (valley, cooler/darker)
"""
from __future__ import annotations
from typing import Generator

from ..constants import PHASE_ELEVATION
from ..map_state import MapGrid, MapConfig, GeneratorProgress
from ..noise_utils import build_perm_table, fbm

SALT_ELEVATION:  int  = 0xE1E2E3E4


def generate_elevation(
    grid:   MapGrid,
    config: MapConfig,
) -> Generator[GeneratorProgress, None, None]:
    """
    Sprint 5 — Elevation Phase.

    Must run AFTER coastline (so water cells are identified) and BEFORE zones.
    Assigns cell.elevation on every land cell using seeded low-frequency FBM.
    Water cells receive elevation = 0.0.
    """
    yield GeneratorProgress(PHASE_ELEVATION, 0.0, 'Computing terrain elevation …')

    perm  = build_perm_table(config.master_seed ^ SALT_ELEVATION)
    rows  = grid.height
    cols  = grid.width

    # Low frequency: 1 cycle per 50 cells (~0.02 cycles/cell)
    freq_r = rows  / 50.0
    freq_c = cols  / 50.0

    for r, row in enumerate(grid.rows()):
        for c, cell in enumerate(row):
            if cell.is_water:
                cell.elevation = 0.0
                continue

            # Sample FBM at low frequency; octaves=3 for smooth hills
            nx = (c / max(cols - 1, 1)) * freq_c
            ny = (r / max(rows - 1, 1)) * freq_r

            raw = fbm(nx, ny, perm, octaves=3, persistence=0.5, lacunarity=2.0)

            # Remap [-1, 1] → [0, 1]
            cell.elevation = max(0.0, min(1.0, (raw + 1.0) * 0.5))

    yield GeneratorProgress(
        PHASE_ELEVATION, 1.0,
        'Elevation layer complete.',
    )
