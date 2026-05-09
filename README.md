# Map Builder — Procedural City Generator

A seed-based procedural city map generator written in Python, with a Pygame visual demo and a text-mode CLI runner. Generates fully game-ready maps with RPG encounter data, building types, landmark injection, and spawn points — deterministically from a single integer seed.

## Quick Start

```bash
pip install pygame
python app.py                           # visual demo (default seed 1, random coast)
python app.py --seed 42 --coast west    # specific seed and coast direction
python app.py --seed 7 --width 160 --height 120
python main.py --seed 7 --width 160 --height 120   # CLI text renderer
```

## Controls (app.py)

| Key | Action |
|---|---|
| `SPACE` | New map (auto-increment seed) |
| `R` | Regenerate same seed (determinism test) |
| `H` | Cycle coast direction: none → N → S → E → W → random |
| `Z` | Toggle zone colour overlay (CBD / Midtown / Residential) |
| `+` / `=` or scroll up | Zoom in |
| `-` or scroll down | Zoom out |
| Arrow keys | Pan when zoomed in |
| `1`–`9` | Jump to that seed directly |
| `Q` / `Esc` | Quit |

## Architecture — Pipeline Phases

The generator runs 10 sequential phases, each yielding `GeneratorProgress` events for non-blocking game-loop integration:

| # | Phase | File | Description |
|---|---|---|---|
| 1 | **Coastline** | `phases/coastline.py` | Perlin FBM + directional gradient → water/land mask with smoothing |
| 2 | **Zones** | `phases/zones.py` | Chebyshev distance from city centre → CBD / Midtown / Residential, with noise-softened boundaries |
| 3 | **Civic Anchor** | `phases/civic.py` | Selects the CBD land cell furthest from water as the city's focal point |
| 4 | **Highways** | `phases/highway.py` | N–S and E–W arterial roads with organic deviation; optional roundabouts and diagonal "Broadway" streets |
| 5 | **Connectors** | `phases/connector.py` | Dense local street grid filling blocks between highways |
| 6 | **Sidewalks** | `phases/sidewalk.py` | 1-cell sidewalk bands on connector-adjacent land with correct bitmask tile selection |
| 7 | **Blocks** | `phases/blocks.py` | Flood-fill interior block detection; exterior cells marked void |
| 8 | **Parks** | `phases/parks.py` | Priority-scored block selection with minimum-separation constraint; count scales dynamically with map size |
| 9 | **Lots** | `phases/lots.py` | Recursive alternating-axis binary split with ±20% noise offset; residential lots get 1-cell setback perimeter |
| 10 | **Buildings** | `phases/buildings.py` | RPG data layer: tile roles, building types, encounter probabilities, landmarks, spawn points |

After lots, a **density post-pass** runs O(N) BFS from highway cells to compute per-cell `density_score` used by the encounter system and building colour variation.

## Generation Parameters (MapConfig)

```python
from map_builder import MapConfig

config = MapConfig(
    width=96,                  # grid columns (default 96 → ~960 m at 10 m/cell)
    height=72,                 # grid rows
    master_seed=1,             # integer seed — same seed always produces identical map
    coast_side='west',         # 'none'|'north'|'south'|'east'|'west'|'random'
    coast_coverage=0.28,       # fraction of map that is water (0.0–0.6)
    coast_noise_scale=3.5,     # lower = smoother coast; higher = jagged
    coast_smoothing_passes=2,  # erosion passes after noise thresholding
    highway_ns_min=2,          # N–S highway count minimum (triangular distribution)
    highway_ns_max=5,          # N–S highway count ceiling
    highway_ew_min=0,          # E–W highway count minimum
    highway_ew_max=3,          # E–W highway count ceiling
    highway_organic=0.3,       # organic deviation 0=perfectly straight
    connector_density=0.70,    # 0=sparse streets 1=full dense grid
    connector_spacing=12,      # E–W cross-street spacing in cells (~120 m)
    avenue_spacing=24,         # N–S avenue spacing in cells (~240 m)
    connector_turn_bias=0.05,  # Perlin drift amplitude for organic streets
    roundabout_count=10,       # max circular junctions
    diagonal_streets=2,        # Broadway / diagonal avenue count
    sidewalk_depth=1,          # cells of sidewalk on each road side
    sidewalk_damage_rate=0.15, # probability a sidewalk tile is cracked/worn variant
)
```

## Game Data Layer

Every `MapCell` after generation carries:

| Field | Type | Description |
|---|---|---|
| `tile_role` | `str` | `ROLE_*` constant — traversability class |
| `building_type` | `str` | `BLDG_*` constant — semantic building label |
| `encounter_chance` | `float` | 0.0–1.0 per-step random encounter probability |
| `is_spawn_point` | `bool` | NPC/enemy spawn origin |
| `landmark_type` | `str` | `'town_hall'` / `'station'` / `'hospital'` / `'police'` / `''` |
| `density_score` | `float` | 0.0–1.0 proximity to highway network |
| `zone_id` | `int` | `ZONE_CBD=0` / `ZONE_MIDTOWN=1` / `ZONE_RESIDENTIAL=2` |
| `is_park` | `bool` | True if cell belongs to a park block |
| `is_setback` | `bool` | True for residential front-yard cells (rendered as lawn) |
| `lot_id` | `int` | ≥ 0 for subdivided building lots; -1 for roads/parks/exterior |

### Tile Roles

| Role constant | String | Meaning |
|---|---|---|
| `ROLE_WALKABLE_HIGHWAY` | `'highway'` | Arterial road — lower encounter, fast traffic |
| `ROLE_WALKABLE_ROAD` | `'road'` | Connector road — standard street danger |
| `ROLE_WALKABLE_ALLEY` | `'alley'` | Short dead-end (≤ 3 cells) — high danger |
| `ROLE_WALKABLE_SIDEWALK` | `'sidewalk'` | Pavement — safe, low encounter |
| `ROLE_WALKABLE_PARK` | `'park'` | Green space — medium encounter, spawn points |
| `ROLE_WALKABLE_PLAZA` | `'plaza'` | Roundabout / market square — scripted events only |
| `ROLE_BUILDING_CBD` | `'bldg_cbd'` | Office tower — obstacle |
| `ROLE_BUILDING_MIDTOWN` | `'bldg_mid'` | Shop / apartment — obstacle |
| `ROLE_BUILDING_RESI` | `'bldg_resi'` | House — obstacle |
| `ROLE_BUILDING_CIVIC` | `'bldg_civic'` | Landmark building — obstacle |
| `ROLE_WATER` | `'water'` | Impassable ocean/river |
| `ROLE_EXTERIOR` | `'exterior'` | Outside any city block — void |

## File Structure

```
GameDev/
├── app.py                  — Pygame visual demo + cell_color() renderer
├── main.py                 — CLI text-mode runner with ASCII map
├── DEVLOG.md               — Sprint-by-sprint development log
├── README.md               — This file
│
├── map_builder/            — Core generation engine (no Pygame dependency)
│   ├── __init__.py         — Public API exports
│   ├── constants.py        — All shared constants (ROLE_*, ZONE_*, BLDG_*, etc.)
│   ├── map_state.py        — MapCell, MapGrid, MapConfig, GeneratorProgress
│   ├── map_generator.py    — MapGenerator — orchestrates full pipeline
│   ├── noise_utils.py      — Pure-Python Perlin noise + FBM
│   ├── tile_registry.py    — Sprite sheet tile descriptor database
│   └── phases/
│       ├── coastline.py    — Phase 1: water/land generation
│       ├── zones.py        — Phase 2: CBD/Midtown/Residential assignment
│       ├── civic.py        — Phase 3: town centre anchor placement
│       ├── highway.py      — Phase 4: arterial road generation
│       ├── connector.py    — Phase 5: local street grid
│       ├── sidewalk.py     — Phase 6: sidewalk tile placement
│       ├── blocks.py       — Phase 7: interior block flood-fill
│       ├── parks.py        — Phase 8: park block selection
│       ├── lots.py         — Phase 9: building lot subdivision + setbacks
│       └── buildings.py    — Phase 10: RPG game data layer
│
├── assets/                 — Sprite sheets (roads.png, sidewalks.png)
└── docs/                   — Sprint research documents
    ├── sprint4_brief.md    — City planning research (parks, waterfront, setbacks)
    └── sprint4_test_results.md — Sprint 4 test results (30 configs, 0 errors)
```

## Usage as a Library

```python
from map_builder import MapGenerator, MapConfig

# Generate a map blocking (e.g. for a server, tool, or test)
config = MapConfig(width=80, height=60, master_seed=42, coast_side='west')
gen = MapGenerator(config)
gen.generate_blocking()

# Read the grid
grid = gen.grid
cell = grid[30][40]          # row 30, column 40
print(cell.tile_role)        # e.g. 'road'
print(cell.building_type)    # e.g. 'shop'
print(cell.encounter_chance) # e.g. 0.142

# Non-blocking game-loop integration
gen_iter = MapGenerator(config).generate()
for progress in gen_iter:
    loading_screen.set_progress(progress.phase, progress.progress, progress.message)
# grid is now fully populated

# Statistics
print(gen.stats)  # seed, size, land/water/road counts, blocks, parks, lots, spawns, time
```

## Determinism Guarantee

Same `master_seed` + same `MapConfig` always produces bit-identical maps. All randomness is derived from `master_seed ^ SALT_*` per-phase constants. You never need to save the full grid — just save the seed and config.

## Dependencies

- **Python 3.10+** (uses `match`-free syntax, compatible with 3.10+)
- **Pygame 2.x** — only required for `app.py` (visual demo); `map_builder` and `main.py` have no external dependencies
