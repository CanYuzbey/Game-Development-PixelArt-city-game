# GameDev — Procedural City Map Builder

A seed-driven procedural city map generator for a mid-rise isometric pixel-art RPG.
Given a single integer seed the engine produces a fully deterministic city layout —
coastline, highways, connector roads with junction markings, roundabouts, and sidewalks —
all backed by calibrated sprite sheet tile coordinates ready for the game renderer.

---

## Quick Start

```bash
# Interactive Pygame viewer (recommended)
python app.py

# Headless ASCII output (no Pygame required)
python main.py --seed 42 --coast west
```

**Requirements:** Python 3.10+ · pygame 2.x

---

## Controls (app.py)

| Key | Action |
|-----|--------|
| `SPACE` | New map (auto-increments seed) |
| `R` | Regenerate same seed (determinism check) |
| `1`–`9` | Jump to that seed |
| `H` | Cycle coast direction (none → N → S → E → W → random) |
| `+` / `-` | Zoom in / out |
| Arrow keys | Pan when zoomed |
| `Q` / `Esc` | Quit |

**Colour legend:**

| Colour | Meaning |
|--------|---------|
| Blue | Water / ocean |
| Brown | Bare land |
| Gold | Highway (yellow arterial — connects districts) |
| Cyan | Connector road (main city street) |
| Bright cyan | Connector road with junction marking |
| Grey | Sidewalk |

---

## Project Structure

```
GameDev/
├── app.py                   # Pygame interactive demo
├── main.py                  # Headless ASCII demo (no Pygame)
├── assets/
│   ├── roads.png            # Road sprite sheet  (1448 × 1086 px)
│   ├── roads_debug.png      # Annotated version for tile calibration
│   ├── sidewalks.png        # Sidewalk sprite sheet
│   └── sidewalks_debug.png
├── Info_memory/
│   └── mapping.txt          # Tile coordinate reference & design notes
└── map_builder/             # Core engine package
    ├── __init__.py          # Public API exports
    ├── constants.py         # All shared string/int constants
    ├── map_state.py         # MapCell, MapGrid, MapConfig, GeneratorProgress
    ├── map_generator.py     # Pipeline orchestrator (yield-based)
    ├── noise_utils.py       # Pure-Python Perlin / FBM noise
    ├── tile_registry.py     # Sprite-sheet pixel coordinates for every tile
    └── phases/
        ├── coastline.py     # Phase 1 — land/water layout
        ├── highway.py       # Phase 2 — highway spines
        ├── connector.py     # Phase 3 — city street grid + junction markings
        └── sidewalk.py      # Phase 4 — sidewalk tile placement
```

---

## Generation Pipeline

Every map runs four deterministic phases in sequence.
The same `master_seed` always produces an identical map.

### Phase 1 — Coastline (`coastline.py`)
- `coast_side = 'none'` → pure inland map, all cells land (no noise, instant).
- `coast_side = 'random'` → 50% chance of a directional coast (N/S/E/W), 50% inland.
- Directional coasts: 4-octave FBM noise blended with a directional gradient,
  thresholded so exactly `coast_coverage` fraction of cells become water,
  then smoothed with 2 majority-vote erosion passes.

### Phase 2 — Highways (`highway.py`)
- N-S count drawn from `triangular(ns_min, ns_max, mode=ns_min)`.
- E-W count drawn from `triangular(ew_min, ew_max, mode=ew_min)`.
- Each highway traced with a noise-biased greedy spine walker (backtracking on dead ends).
- Rendered gold in the demo; no sidewalks (traffic arteries only).

### Phase 3 — Connector Roads (`connector.py`)
Six passes in order:

| Pass | What it does |
|------|-------------|
| 1 | N-S avenues spaced `avenue_spacing` cells apart (Perlin drift ±1) |
| 2 | E-W cross-streets spaced `connector_spacing` cells apart |
| 2.5 | Gap-fill: secondary streets added wherever dropped streets left a block > 1.5× intended size |
| 3 | Diagonal Broadway-style streets (noise-biased spine tracer, NW→SE) |
| 4 | Bitmask resolution: each road cell gets its correct structural tile (straight / corner / T / X) |
| 4b | Surface variation: straight tiles randomly pick from plain / dashed / yellow-line sprite variants |
| 5 | Roundabout placement at T/X junctions; 3×3 tile blocks, spaced ≥ `connector_spacing × 2` |
| 6 | Junction markings: crosswalks at every X-junction; yield/arrow at 60% of T-junctions |

### Phase 4 — Sidewalks (`sidewalk.py`)
- Pass A: mark all land cells adjacent to connector roads.
- Pass B: bitmask → correct sidewalk tile (edge / corner / T / X / surface).

---

## Configuration (`MapConfig`)

All parameters live in `map_builder/map_state.py`.
Pass them explicitly to `MapConfig(...)` or use the defaults.

### Size
| Param | Default | Range | Notes |
|-------|---------|-------|-------|
| `width` | 160 | 16–256 | Grid columns (10 m/cell → 1.6 km) |
| `height` | 120 | 16–256 | Grid rows (10 m/cell → 1.2 km) |
| `master_seed` | 1 | any int | Same seed = identical map |

### Coastline
| Param | Default | Notes |
|-------|---------|-------|
| `coast_side` | `'none'` | `'none'` \| `'north'` \| `'south'` \| `'east'` \| `'west'` \| `'random'` |
| `coast_coverage` | 0.30 | Fraction of map that is water (0–0.65) |
| `coast_noise_scale` | 3.5 | Lower = smoother coast; higher = jagged |
| `coast_smoothing_passes` | 2 | Erosion passes (0–5) |

### Highways (yellow)
| Param | Default | Notes |
|-------|---------|-------|
| `highway_ns_min` | 2 | N-S highway minimum (mode of triangular distribution) |
| `highway_ns_max` | 4 | N-S highway ceiling |
| `highway_ew_min` | 0 | E-W highway minimum |
| `highway_ew_max` | 2 | E-W highway ceiling |
| `highway_organic` | 0.3 | Waviness: 0 = straight, 1 = very organic |

### Connector Roads (blue / city streets)
| Param | Default | Notes |
|-------|---------|-------|
| `avenue_spacing` | 15 | N-S avenue spacing in cells (~150 m) |
| `connector_spacing` | 6 | E-W cross-street spacing in cells (~60 m) |
| `connector_density` | 0.85 | Fraction of grid lines actually placed (0–1) |
| `min_block_depth` | 2 | Minimum clear cells between parallel roads |
| `connector_turn_bias` | 0.05 | Perlin drift amplitude (0 = dead-straight) |
| `diagonal_streets` | 2 | Broadway-style diagonal count (0–4) |
| `roundabout_count` | 15 | Maximum roundabout 3×3 blocks per map |

### Sidewalks
| Param | Default | Notes |
|-------|---------|-------|
| `sidewalk_damage_rate` | 0.15 | Probability a sidewalk tile uses a worn/cracked variant |

---

## Sprite Sheet Layout

### `roads.png` (1448 × 1086 px)
| Band | y | h | Tiles | Used for |
|------|---|---|-------|----------|
| 0 | 15 | 100 | 8 | Surface variants (plain, dashed, yellow line, dark) |
| 2 | 241 | 80 | 12 | Junction markings (crosswalk, arrows, yield, fork, merge) |
| 3 | 344 | 98 | 9 | Structural tiles (X, T×4, straight, corner×2) |
| 4 | 461 | 102 | 8 | Highway elevated deck tiles |
| 5 | 580 | 380 | 9 | Roundabout 3×3 grid |
| 6 | 989 | 64 | 12 | Road props (cones, lamps, barriers) |

### `sidewalks.png` (1448 × 1086 px)
| Band | y | h | Tiles | Used for |
|------|---|---|-------|----------|
| 0 | 37 | 102 | 10 | Surface variants |
| 1 | 168 | 114 | 10 | Corners, T/X junctions, end caps |
| 2 | 317 | 123 | 7 | Straight edges, inner curves, roundabout arcs |
| 4 | 477 | 118 | 9 | Ramps, tactile paving strips |
| 5 | 628 | 114 | 10 | Tactile variants, grates, planters |
| 6 | 769 | 114 | 10 | Worn concrete, utility covers |
| 7 | 901 | 130 | 15 | Props (bollards, signs, bins, debris) |

**Connectivity bitmask convention** (same for roads and sidewalks):
```
Bit 3 (8) = North   Bit 2 (4) = East
Bit 1 (2) = South   Bit 0 (1) = West

Example: 0b1010 = N+S connected → straight N-S road tile
```

---

## Cell Layers

Each `MapCell` holds four independent layers:

| Constant | Index | Content |
|----------|-------|---------|
| `LAYER_GROUND` | 0 | Land or water base tile |
| `LAYER_ROAD` | 1 | Structural road tile (highway or connector) |
| `LAYER_SIDEWALK` | 2 | Sidewalk tile |
| `LAYER_DECOR` | 3 | Junction marking overlay (crosswalk, yield, arrows) |

Access in the game renderer:
```python
tile_id  = cell.layers[LAYER_ROAD]          # e.g. 'road_1111'
var_idx  = cell.variation[LAYER_ROAD]       # picks the sprite variant
tile_def = REGISTRY.get_variants(tile_id)[var_idx]
rect     = tile_def.pixel_rect              # (left, top, w, h) on sprite sheet
sheet    = tile_def.sprite_sheet            # 'roads' or 'sidewalks'
```

---

## Integrating into the Game Engine

```python
from map_builder import MapGenerator, MapConfig

config = MapConfig(
    width       = 160,
    height      = 120,
    master_seed = save_file.seed,
    coast_side  = 'random',
)

generator = MapGenerator(config)

# Non-blocking (game loop):
gen = generator.generate()
progress = next(gen)          # call once per frame; exhausted = map ready

# Blocking (server / tool):
generator.generate_blocking()
grid = generator.grid
```

Serialise and reload without storing the full grid:
```python
data = generator.to_dict()    # store seed + config in save file
g2   = MapGenerator.from_dict(data)
g2.generate_blocking()        # identical map, zero save overhead
```

---

## Bugfixing Guide

### "All cells are water / no roads appear"
- `coast_coverage` too high (> 0.65). Lower it.
- `coast_side = 'none'` should give all-land — verify `cell.is_land` is True everywhere.

### "Assertion error on MapConfig"
- `avenue_spacing` must be ≥ `connector_spacing`.
- `coast_coverage` must be ≤ 0.65.
- `width` / `height` must be 16–256.

### "Highways missing or too short"
- `highway_ns_min = 0` and `highway_ew_min = 0` → some seeds produce 0 highways. Expected.
- If highways abort mid-trace, the land area may be too fragmented (high `coast_coverage` + jagged noise). Reduce `coast_noise_scale`.

### "No roundabouts placed"
- Roundabouts need a 3×3 all-land block centred on a T/X junction.
- If the map is too small or too coastal, qualifying junctions may not exist.
- Reduce `roundabout_count` expectation or lower `coast_coverage`.

### "Road bitmask tile looks wrong (wrong corner/T direction)"
- Check `grid.road_bitmask(r, c)` against `ROAD_BITMASK_TO_TILE` in `constants.py`.
- Bitmask is computed from the 4 cardinal neighbours — verify neighbour cells have `is_road = True`.

### "Sprite rect out of bounds / wrong tile drawn"
- All pixel coordinates are in `tile_registry.py`. Cross-reference against `roads_debug.png` / `sidewalks_debug.png`.
- Run `python -c "from map_builder.tile_registry import REGISTRY; print(REGISTRY.summary())"` to dump every registered rect.

### Determinism check
```bash
python main.py --seed 7 --no-render | grep "Roads"
python main.py --seed 7 --no-render | grep "Roads"
# Both lines must be identical
```

---

## Adding a New Road Tile Variant

1. Measure the pixel rect from the sprite sheet (use `roads_debug.png`).
2. Add a `_r(left, top, w, h, 'label')` entry to the relevant tile list in `tile_registry.py`.
3. The `variation` index stored per-cell selects which entry in the list is rendered.
4. No changes needed elsewhere — the registry resolves everything at runtime.

---

## Author

**CanYüzbey** — solo developer (game design · art · pixel art · procedural algorithms)
