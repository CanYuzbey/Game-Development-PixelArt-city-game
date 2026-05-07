"""
map_builder/noise_utils.py
───────────────────────────
Pure-Python gradient noise + FBM (Fractional Brownian Motion).
No external dependencies — safe to ship in any environment.

Algorithm: classic Perlin gradient noise with quintic interpolation.
Reference: Ken Perlin (2002), "Improving Noise". SIGGRAPH.
"""
from __future__ import annotations
import math
import random
from typing import Sequence


# 2-D gradient vectors (8 directions, unit length)
_GRAD2 = [
    ( 1.0,  0.0), (-1.0,  0.0), ( 0.0,  1.0), ( 0.0, -1.0),
    ( 0.7071,  0.7071), (-0.7071,  0.7071),
    ( 0.7071, -0.7071), (-0.7071, -0.7071),
]


# ── Permutation table ─────────────────────────────────────────────────────────

def build_perm_table(seed: int) -> list[int]:
    """
    Build a seeded permutation table of length 512.
    Deterministic for a given seed — same seed always produces the same noise.
    """
    rng = random.Random(seed)
    p = list(range(256))
    rng.shuffle(p)
    return p + p   # doubled to avoid index wrapping


# ── Core noise functions ──────────────────────────────────────────────────────

def _fade(t: float) -> float:
    """Quintic ease curve — eliminates visible grid artifacts at integer coords."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _grad2(perm: list[int], ix: int, iy: int) -> tuple[float, float]:
    """Pick a gradient vector deterministically from the permutation table."""
    return _GRAD2[perm[(perm[ix & 255] + iy) & 255] & 7]


def noise2d(x: float, y: float, perm: list[int]) -> float:
    """
    Sample 2-D gradient noise at (x, y).
    Returns a value in approximately [-1, 1].
    The permutation table `perm` encodes the seed.
    """
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    u  = _fade(fx)
    v  = _fade(fy)

    g00 = _grad2(perm, ix,     iy    )
    g10 = _grad2(perm, ix + 1, iy    )
    g01 = _grad2(perm, ix,     iy + 1)
    g11 = _grad2(perm, ix + 1, iy + 1)

    n00 = g00[0] * fx       + g00[1] * fy
    n10 = g10[0] * (fx - 1) + g10[1] * fy
    n01 = g01[0] * fx       + g01[1] * (fy - 1)
    n11 = g11[0] * (fx - 1) + g11[1] * (fy - 1)

    return _lerp(_lerp(n00, n10, u), _lerp(n01, n11, u), v)


def fbm(
    x: float,
    y: float,
    perm: list[int],
    octaves:     int   = 4,
    persistence: float = 0.5,
    lacunarity:  float = 2.0,
) -> float:
    """
    Fractional Brownian Motion — sum of noise octaves at increasing frequency.

    Args:
        x, y:        World-space coordinates (divide by map size before calling).
        perm:        Permutation table from build_perm_table().
        octaves:     How many noise layers to sum (4 = good coastlines).
        persistence: How much each octave's amplitude shrinks (0.5 = halved).
        lacunarity:  How much each octave's frequency grows  (2.0 = doubled).

    Returns:
        Float in approximately [-1, 1] (normalised by max possible amplitude).
    """
    value      = 0.0
    amplitude  = 1.0
    frequency  = 1.0
    max_value  = 0.0

    for _ in range(octaves):
        value     += noise2d(x * frequency, y * frequency, perm) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    return value / max_value  # normalise to [-1, 1]


# ── Directional bias helper ────────────────────────────────────────────────────

def directional_gradient(
    row: int,
    col: int,
    map_height: int,
    map_width:  int,
    coast_side: str,
    steepness:  float = 2.5,
) -> float:
    """
    Return a bias value in [0, 1] that pushes land toward the opposite side
    of the map from `coast_side`.

    steepness > 1 creates a sharper coast boundary.
    steepness < 1 creates a very gradual gradient.
    """
    if coast_side == 'west':
        t = col / (map_width - 1)          # 0 at west coast, 1 at east
    elif coast_side == 'east':
        t = 1.0 - col / (map_width - 1)
    elif coast_side == 'north':
        t = row / (map_height - 1)
    elif coast_side == 'south':
        t = 1.0 - row / (map_height - 1)
    else:
        return 0.5                          # 'none' → uniform, no coast bias

    # Smoothstep + power curve for sharper coast boundary
    t = t * t * (3.0 - 2.0 * t)           # smoothstep
    return pow(t, 1.0 / steepness)


def smooth_land_grid(
    land: list[list[bool]],
    passes: int = 2,
) -> list[list[bool]]:
    """
    Proportional majority-vote erosion filter.

    A cell becomes land if STRICTLY MORE THAN HALF of its in-bounds Moore
    neighbours (including itself) are land.  Out-of-bounds cells are simply
    not counted, so corner and edge cells are judged against 4 or 6 real
    neighbours instead of a fixed threshold of 5.

    The original threshold-of-5 rule treated all out-of-bounds as water,
    which caused corners (only 4 reachable cells) to ALWAYS convert to water
    regardless of the noise value, producing a blue artefact at every map
    corner that cascaded inward across multiple passes.

    Fix: use  count * 2 > total_in_bounds  (strict majority of real cells).
    Interior cells (9 neighbours): need 5+  → identical behaviour to before.
    Edge   cells  (6 neighbours): need 4+  → 66% threshold, not 83%.
    Corner cells  (4 neighbours): need 3+  → 75% threshold, never automatic water.
    """
    rows = len(land)
    cols = len(land[0])

    for _ in range(passes):
        new_land = [row[:] for row in land]
        for r in range(rows):
            for c in range(cols):
                land_count  = 0
                total_count = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            land_count  += int(land[nr][nc])
                            total_count += 1
                # Strict majority of actual in-bounds neighbours
                new_land[r][c] = land_count * 2 > total_count
        land = new_land

    return land
