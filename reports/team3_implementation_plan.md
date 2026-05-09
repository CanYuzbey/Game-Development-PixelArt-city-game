# Team 3 — Senior Development Implementation Plan
**Date:** 2026-05-09
**Source Branch:** `claude/hopeful-babbage-ad0877`
**Target Merge:** `map-design`
**Audience:** Coding agents (Team 4) and verification agents (Team 5)

---

## Section 1: Gap Analysis

| Feature | Research Priority | Current State | Gap |
|---|---|---|---|
| Zone-tinted land colors in app.py | HIGH (Team 1: visible zone differentiation is the #1 realism signal) | app.py uses a single flat `C_LAND = (112,97,72)` for all land cells regardless of zone | Zone colors computed in zones.py but never passed to renderer |
| Block detection (BFS enclosed regions) | HIGH (Team 2: "enables everything below", #1 ranked algorithm) | Not implemented. No phase exists to label enclosed land areas | No `blocks.py`, no `block_id` on MapCell |
| Lot/parcel subdivision | HIGH (Team 2: ranked #2; Parish & Müller OBB splitting) | Not implemented | No `lots.py`, no `lot_id` on MapCell |
| Park placement by zone and block size | HIGH (Team 1: park-to-block ratio, zone-specific placement; Team 2: ranked #3) | Not implemented | No `parks.py`, no PARK tile type |
| Building density gradient | HIGH (Team 1: density transitions; Team 2: ranked #4 density score) | `zone_id` exists on MapCell but no `density_score`. No downstream use | `density_score` field missing; zones.py does not compute proximity bonuses |
| Zone character overlay in main.py | LOW (helpful for dev verification) | main.py renders `.` for all land with no zone distinction | No zone-aware glyph logic |
| Branch merge (worktree → map-design) | CRITICAL (operational) | Two commits on `claude/hopeful-babbage-ad0877` not on `map-design`: zones phase, organic streets, cul-de-sacs | app.py on `map-design` will not see zones.py or cul-de-sac work |
| Multi-tier road widths | MED (Team 1: "single largest visual impact") | Highway vs connector visual difference exists (gold vs cyan) but cell width is always 1 tile | Single-tile roads only; multi-width requires renderer changes not in scope |
| Cul-de-sacs in Residential only | DONE | connector.py Pass 4c already sprouts cul-de-sac stubs in ZONE_RESIDENTIAL | No gap |
| Roundabouts at junctions | DONE | connector.py Pass 5 already places 3×3 roundabout tiles | No gap |
| Diagonal Broadway-style streets | DONE | connector.py Pass 3 already traces NW→SE diagonals | No gap |
| Zone-aware connector density | DONE | `_zone_score()` in connector.py modulates `eff_density` by edge distance | No gap |
| Spatially-correlated dropout | PARTIAL | Flat per-zone dropout exists; noise-correlated dropout (Team 2 §6.3) not implemented | Could improve realism but is a parameter tweak, not a structural gap |
| WFC visual post-pass | LOW (Team 2: ranked #10, 150-200 LOC, Medium difficulty) | Not implemented | Out of scope for this sprint — too large, too risky |
| CBD civic anchor / landmark seed | MED (Team 2 §4.1, Team 1 §5) | Not implemented | Useful but depends on block detection; add as Unit 8 |
| Noise-offset connector spacing (irregular blocks) | LOW (Team 2 §6.1, ranked #8) | Fixed spacing only | Small improvement; add as Unit 9 |

---

## Section 2: Implementation Units

---

## Unit 1 — Branch Merge: `claude/hopeful-babbage-ad0877` → `map-design`

**Priority:** HIGH
**Files to modify:** None (git operation only)
**New files to create:** None
**Estimated LOC:** 0
**Dependencies:** None

### What to implement
- Run `git merge claude/hopeful-babbage-ad0877` from the `map-design` branch
- The two commits to merge are:
  - `a15a056` — City realism overhaul: zones, organic streets, cul-de-sacs
  - `0fcb68a` — Initial commit — procedural city map builder engine
- The diff includes: `map_builder/phases/zones.py` (new file, 77 lines), updates to `connector.py` (+131 LOC for cul-de-sacs, roundabout markings, zone-aware drift), `highway.py` (+41 LOC for N-S/E-W axis split), `map_state.py` (+25 LOC for `zone_id` field), `constants.py` (+8 LOC for zone constants)
- After merge, verify `python app.py` still launches without errors
- After merge, verify `python main.py --no-render` completes the full pipeline

### Algorithm
```
git checkout map-design
git merge claude/hopeful-babbage-ad0877 --no-ff -m "Merge city realism overhaul from hopeful-babbage-ad0877"
python app.py --seed 1 --coast none --width 64 --height 48   # smoke test
python main.py --no-render --seed 1                           # smoke test
```

### Acceptance criteria
- `git log --oneline map-design | head -3` shows the two new commits
- `python app.py` launches the Pygame window without ImportError or AttributeError
- `python main.py --no-render` prints all phase headers (COASTLINE, ZONES, HIGHWAY, CONNECTOR, SIDEWALK, COMPLETE) and exits cleanly
- `zones.py` is importable from `map_design` branch

---

## Unit 2 — Zone Colors and Toggle in `app.py`

**Priority:** HIGH
**Files to modify:** `app.py` (worktree path: `map_builder/` siblings — edit the file at the repo root)
**New files to create:** None
**Estimated LOC:** 55
**Dependencies:** Unit 1 (zones must be merged so zone_id is available on MapCell)

### What to implement
- Add three zone-tinted land colors as named constants near the existing palette:
  - `C_LAND_CBD        = (196, 168, 130)` — warm tan (urban dry concrete)
  - `C_LAND_MIDTOWN    = (150, 168, 123)` — grey-green (mixed vegetation)
  - `C_LAND_RESIDENTIAL = (122, 158, 110)` — muted green (residential lawns)
- Add a park color constant:
  - `C_PARK            = ( 72, 140,  72)` — park green (used by Unit 4)
- Add a module-level boolean `_zone_mode: bool = False`
- Modify `cell_color(cell)` so that when `_zone_mode` is True and `cell.is_land` (and cell is not a park — see Unit 4), return the appropriate zone color based on `cell.zone_id`:
  - `ZONE_CBD` → `C_LAND_CBD`
  - `ZONE_MIDTOWN` → `C_LAND_MIDTOWN`
  - `ZONE_RESIDENTIAL` → `C_LAND_RESIDENTIAL`
  - fallback → `C_LAND` (existing brown)
- In `_handle_events()`, add a `elif key == pygame.K_z:` branch that toggles `_zone_mode` and calls `self._refresh_cell_surf()`
- Update the key hints string in `_draw_hud()` to include `Z zone` in the hint line
- Update the legend swatches list in `_draw_hud()` to include the three zone swatches when `_zone_mode` is True (replace the single `C_LAND 'land'` swatch with three zone swatches)
- Import `ZONE_CBD`, `ZONE_MIDTOWN`, `ZONE_RESIDENTIAL` from `map_builder.constants` at the top of `app.py`

### Algorithm
```python
# 1. Add near existing palette constants (after C_LAND line):
C_LAND_CBD         = (196, 168, 130)
C_LAND_MIDTOWN     = (150, 168, 123)
C_LAND_RESIDENTIAL = (122, 158, 110)
C_PARK             = ( 72, 140,  72)

# 2. Add module-level toggle (after _COASTS list):
_zone_mode: bool = False

# 3. Modify cell_color():
def cell_color(cell) -> tuple[int, int, int]:
    if cell.is_water:
        return C_WATER
    if cell.is_road:
        if cell.road_category == ROAD_HIGHWAY:
            return C_HIGHWAY
        if cell.layers.get(LAYER_DECOR) is not None:
            return (90, 215, 240)
        return C_CONNECTOR
    if cell.is_sidewalk:
        return C_SIDEWALK
    if cell.is_land:
        # Check park first (Unit 4 sets tile_type; if not present, skip)
        if getattr(cell, 'is_park', False):
            return C_PARK
        if _zone_mode:
            return {
                ZONE_CBD:         C_LAND_CBD,
                ZONE_MIDTOWN:     C_LAND_MIDTOWN,
                ZONE_RESIDENTIAL: C_LAND_RESIDENTIAL,
            }.get(cell.zone_id, C_LAND)
        return C_LAND
    return C_UNINIT

# 4. In _handle_events(), add after the K_h branch:
elif key == pygame.K_z:
    global _zone_mode
    _zone_mode = not _zone_mode
    self._refresh_cell_surf()

# 5. Update hints string to include 'Z zone':
hints = 'SPACE new  R redo  H coast  Z zone  +/- zoom  arrows pan  1-9 seed  Q quit'

# 6. Update legend swatches conditional on _zone_mode:
if _zone_mode:
    swatches = [
        (C_WATER,            'water'),
        (C_LAND_CBD,         'CBD'),
        (C_LAND_MIDTOWN,     'midtown'),
        (C_LAND_RESIDENTIAL, 'residential'),
        (C_HIGHWAY,          'highway'),
        (C_CONNECTOR,        'road'),
        (C_SIDEWALK,         'sidewalk'),
    ]
else:
    swatches = [  # existing list unchanged ]
```

### Acceptance criteria
- `python app.py` launches without error
- Pressing `Z` toggles zone-color mode; land cells change color; pressing `Z` again reverts to uniform tan
- In zone mode, the CBD ring (center cells) displays warm tan `(196, 168, 130)`, outer cells display green `(122, 158, 110)`
- Water, highway, connector, and sidewalk cells are unaffected by zone mode toggle
- The HUD legend updates to show three zone swatches when zone mode is active
- Key hint line shows `Z zone`
- `R` and `SPACE` preserve the current `_zone_mode` state (do not reset it on regenerate)

---

## Unit 3 — Block Detection Phase

**Priority:** HIGH
**Files to modify:**
- `map_builder/map_state.py` — add `block_id: int = -1` field to `MapCell`
- `map_builder/constants.py` — add `PHASE_BLOCKS`, `SALT_BLOCKS`, `BLOCK_EXTERIOR_ID` constants
- `map_builder/map_generator.py` — add `_run_phase_blocks()` and call it after sidewalks; store `self.blocks` list
**New files to create:**
- `map_builder/phases/blocks.py`
**Estimated LOC:** 95
**Dependencies:** None (can run after Unit 1 merge)

### What to implement
- In `constants.py`, add:
  - `PHASE_BLOCKS: Final[str] = 'blocks'`
  - `SALT_BLOCKS: Final[int] = 0x789ABC`
  - `BLOCK_EXTERIOR_ID: Final[int] = -1` (marks cells that touch the map edge — exterior)
- In `map_state.py`, add to `MapCell` dataclass:
  - `block_id: int = -1` (default -1 = unassigned; exterior cells stay -1; interior blocks get 0, 1, 2, ...)
  - `is_park: bool = False` (placeholder used by Unit 4; default False so old maps load cleanly)
- In `blocks.py`, implement `generate_blocks(grid, config)` as a yield-based generator:
  - Determine which cell types count as "road" for BFS boundary: any cell where `cell.is_road` is True
  - BFS flood-fill scan: for every non-road, unvisited cell, start a BFS region
  - During BFS, track whether the region touches any map-edge cell (row==0, row==height-1, col==0, col==width-1)
  - After BFS completes: if `touches_edge` is True, assign `block_id = BLOCK_EXTERIOR_ID` (-1) to all region cells; else assign the next sequential block_id integer (0-based counter)
  - Store all non-exterior block cell sets in a list; write `block_id` to each `MapCell` in the set
  - After completing all regions, store the list as a local variable and yield it back via the generator's completion message
  - The generator must yield at least two `GeneratorProgress` events: one at start (0.0) and one at end (1.0) with the count of interior blocks found
- In `map_generator.py`:
  - Import `generate_blocks` from `phases.blocks`
  - Add `self.blocks: list[set] = []` to `__init__`
  - Add `_run_phase_blocks()` method that calls `generate_blocks` and captures the block list from the generator's side-effect (since the phase modifies `grid` in place, `self.blocks` can be populated by reading all cells after the phase completes, or by having `generate_blocks` accept a `sink` list parameter)
  - Call `yield from self._run_phase_blocks()` after `yield from self._run_phase_sidewalks()` in `generate()`
  - Update `stats` dict in `generate()` to include `'blocks': len(self.blocks)`

### Algorithm
```python
# blocks.py

from collections import deque
from ..constants import PHASE_BLOCKS, BLOCK_EXTERIOR_ID
from ..map_state import MapGrid, MapConfig, GeneratorProgress

def generate_blocks(
    grid: MapGrid,
    config: MapConfig,
    sink: list | None = None,   # if provided, appended with block cell sets
) -> Generator[GeneratorProgress, None, None]:

    yield GeneratorProgress(PHASE_BLOCKS, 0.0, 'Detecting city blocks via BFS …')

    rows, cols = grid.height, grid.width
    visited = [[False] * cols for _ in range(rows)]
    block_counter = 0
    found_blocks = []

    for start_r in range(rows):
        for start_c in range(cols):
            cell = grid[start_r][start_c]
            if visited[start_r][start_c] or cell.is_road:
                visited[start_r][start_c] = True
                continue

            # BFS this region
            region = []
            queue = deque([(start_r, start_c)])
            visited[start_r][start_c] = True
            touches_edge = False

            while queue:
                r, c = queue.popleft()
                region.append((r, c))
                if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                    touches_edge = True
                for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if not visited[nr][nc] and not grid[nr][nc].is_road:
                            visited[nr][nc] = True
                            queue.append((nr, nc))

            if touches_edge:
                for r, c in region:
                    grid[r][c].block_id = BLOCK_EXTERIOR_ID
            else:
                bid = block_counter
                block_counter += 1
                block_set = set(region)
                for r, c in region:
                    grid[r][c].block_id = bid
                found_blocks.append(block_set)

    if sink is not None:
        sink.extend(found_blocks)

    yield GeneratorProgress(
        PHASE_BLOCKS, 1.0,
        f'Block detection complete — {block_counter} interior blocks found.'
    )
```

### Acceptance criteria
- `python main.py --no-render` outputs a `[BLOCKS      ]` phase line
- After generation, every land cell has `block_id >= 0` (interior block) or `block_id == -1` (exterior or road)
- Road cells retain `block_id == -1` (they are skipped by BFS)
- `generator.stats['blocks']` contains an integer > 0
- Running the same seed twice produces the same block count (deterministic)
- Water cells that are enclosed by land are assigned a block_id (they are non-road cells and BFS will label them) — this is acceptable; parks phase will not convert water cells

---

## Unit 4 — Park Placement Phase

**Priority:** HIGH
**Files to modify:**
- `map_builder/constants.py` — add park-related constants
- `map_builder/map_state.py` — `is_park: bool` field (added in Unit 3; verify present)
- `map_builder/map_generator.py` — add `_run_phase_parks()` after blocks phase
- `app.py` — `C_PARK` color and `is_park` branch in `cell_color()` (Unit 2 adds this; verify present)
**New files to create:**
- `map_builder/phases/parks.py`
**Estimated LOC:** 90
**Dependencies:** Unit 3 (needs block detection to be complete first)

### What to implement
- In `constants.py`, add:
  - `PARK_SMALL_BLOCK_MAX: Final[int] = 12` — blocks with area < 12 cells in CBD/Midtown become parks
  - `PARK_RESIDENTIAL_MAX_AREA: Final[int] = 40` — max cells for a residential park block
  - `PARK_RESIDENTIAL_MIN_AREA: Final[int] = 15` — min cells for a residential park block
  - `PARK_RESIDENTIAL_PROBABILITY: Final[float] = 0.25` — 25% chance a qualifying residential block becomes a park
  - `SALT_PARKS: Final[int] = 0xA1B2C3`
  - `PHASE_PARKS: Final[str] = 'parks'`
- In `parks.py`, implement `generate_parks(grid, config, blocks)` as a yield-based generator:
  - Accept the `blocks` list (list of sets of `(row, col)` tuples) from `map_generator`
  - For each block:
    - Get zone_id by sampling the zone_id of the first cell in the block
    - CBD or Midtown: if `len(block) < PARK_SMALL_BLOCK_MAX`, mark as park
    - Residential: if `PARK_RESIDENTIAL_MIN_AREA <= len(block) <= PARK_RESIDENTIAL_MAX_AREA` and `rng.random() < PARK_RESIDENTIAL_PROBABILITY`, mark as park
    - "Mark as park": set `cell.is_park = True` on every cell in the block
  - Yield progress at start and end
- In `map_generator.py`:
  - Import and wire `generate_parks`; pass `self.blocks` as argument
  - Call after blocks phase
  - Add `'parks'` key to stats

### Algorithm
```python
# parks.py

import random
from ..constants import (
    PHASE_PARKS, SALT_PARKS,
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    PARK_SMALL_BLOCK_MAX,
    PARK_RESIDENTIAL_MIN_AREA, PARK_RESIDENTIAL_MAX_AREA,
    PARK_RESIDENTIAL_PROBABILITY,
)
from ..map_state import MapGrid, MapConfig, GeneratorProgress

def generate_parks(
    grid: MapGrid,
    config: MapConfig,
    blocks: list,
) -> Generator[GeneratorProgress, None, None]:

    yield GeneratorProgress(PHASE_PARKS, 0.0, 'Placing parks …')

    rng = random.Random(config.master_seed ^ SALT_PARKS)
    park_count = 0

    for i, block in enumerate(blocks):
        if not block:
            continue
        area = len(block)
        sample_r, sample_c = next(iter(block))
        zone = grid[sample_r][sample_c].zone_id
        make_park = False

        if zone in (ZONE_CBD, ZONE_MIDTOWN):
            # Small residual blocks (alleys, dead triangles) become pocket parks
            if area < PARK_SMALL_BLOCK_MAX:
                make_park = True
        elif zone == ZONE_RESIDENTIAL:
            # Medium blocks that could plausibly be a neighborhood park
            if PARK_RESIDENTIAL_MIN_AREA <= area <= PARK_RESIDENTIAL_MAX_AREA:
                if rng.random() < PARK_RESIDENTIAL_PROBABILITY:
                    make_park = True

        if make_park:
            for r, c in block:
                cell = grid[r][c]
                cell.is_park = True
            park_count += 1

        if i % 50 == 0:
            yield GeneratorProgress(
                PHASE_PARKS,
                i / max(len(blocks), 1),
                f'Parks: {park_count} placed so far …'
            )

    yield GeneratorProgress(
        PHASE_PARKS, 1.0,
        f'Park placement complete — {park_count} parks placed.'
    )
```

### Acceptance criteria
- `python main.py --no-render` outputs a `[PARKS       ]` phase line after `[BLOCKS      ]`
- `generator.stats['parks']` is an integer >= 0
- In `app.py` with `Z` zone mode on, park blocks appear in the distinct `C_PARK` green color `(72, 140, 72)` rather than the zone land color
- CBD zone contains at least some park cells (small blocks should qualify)
- Residential zone contains park cells (probability 0.25 over qualifying blocks)
- No road cell or water cell has `is_park = True`
- Regenerating the same seed produces the same park distribution

---

## Unit 5 — Lot Subdivision Markers

**Priority:** MED
**Files to modify:**
- `map_builder/map_state.py` — add `lot_id: int = -1` field to `MapCell`
- `map_builder/constants.py` — add `PHASE_LOTS`, `SALT_LOTS` constants
- `map_builder/map_generator.py` — add `_run_phase_lots()`, call after parks phase, store `self.lots`
**New files to create:**
- `map_builder/phases/lots.py`
**Estimated LOC:** 110
**Dependencies:** Unit 3 (needs block_id on cells), Unit 4 (skip park blocks)

### What to implement
- In `constants.py`, add:
  - `PHASE_LOTS: Final[str] = 'lots'`
  - `SALT_LOTS: Final[int] = 0xD4E5F6`
  - `LOT_MIN_WIDTH: Final[int] = 2` — minimum lot width in cells (20m at 10m/cell)
  - `LOT_MIN_DEPTH: Final[int] = 2` — minimum lot depth in cells
- In `map_state.py`, add to `MapCell`:
  - `lot_id: int = -1` (default -1 = no lot; assigned during subdivision)
- In `lots.py`, implement `generate_lots(grid, config, blocks)`:
  - Skip any block where any cell has `is_park = True`
  - For each non-park block, call `_subdivide_block(block_cells, rng, lot_counter)` to recursively split it
  - Use alternating-axis splitting (see Team 2 §7.2 pseudocode): split the longer dimension first, alternate axes on recursion, add ±20% noise offset to the split position
  - Stop recursing when both dimensions are < `LOT_MIN_WIDTH * 2` and `LOT_MIN_DEPTH * 2`
  - For each resulting lot, assign a sequential `lot_id` integer to all cells in the lot
  - Write `lot_id` to each `MapCell` in place
  - Yield progress periodically; yield completion with total lot count
- In `map_generator.py`:
  - Add `self.lots: list[set] = []` to `__init__`
  - Wire `_run_phase_lots()` to call `generate_lots` passing `self.blocks`
  - Add `'lots'` to stats

### Algorithm
```python
# lots.py

import random
from ..constants import PHASE_LOTS, SALT_LOTS, LOT_MIN_WIDTH, LOT_MIN_DEPTH
from ..map_state import MapGrid, MapConfig, GeneratorProgress

def _subdivide_block(block_cells, rng, lot_id_counter, min_w, min_d):
    """
    Recursive alternating-axis binary split.
    Returns list of (lot_id, frozenset of (r,c)) tuples.
    lot_id_counter is a list[int] used as a mutable reference.
    """
    if not block_cells:
        return []
    rows_list = [r for r, c in block_cells]
    cols_list = [c for r, c in block_cells]
    r_min, r_max = min(rows_list), max(rows_list)
    c_min, c_max = min(cols_list), max(cols_list)
    height = r_max - r_min + 1
    width  = c_max - c_min + 1

    can_split_h = height >= min_d * 2
    can_split_v = width  >= min_w * 2

    if not can_split_h and not can_split_v:
        lid = lot_id_counter[0]
        lot_id_counter[0] += 1
        return [(lid, block_cells)]

    split_horizontal = (height >= width) if can_split_h else False
    if not can_split_h:
        split_horizontal = False
    if not can_split_v:
        split_horizontal = True

    if split_horizontal:
        mid = (r_min + r_max) // 2
        offset = int(rng.uniform(-height * 0.2, height * 0.2))
        split_row = max(r_min + min_d, min(r_max - min_d, mid + offset))
        top    = {(r, c) for r, c in block_cells if r <= split_row}
        bottom = {(r, c) for r, c in block_cells if r > split_row}
        return (_subdivide_block(top, rng, lot_id_counter, min_w, min_d) +
                _subdivide_block(bottom, rng, lot_id_counter, min_w, min_d))
    else:
        mid = (c_min + c_max) // 2
        offset = int(rng.uniform(-width * 0.2, width * 0.2))
        split_col = max(c_min + min_w, min(c_max - min_w, mid + offset))
        left  = {(r, c) for r, c in block_cells if c <= split_col}
        right = {(r, c) for r, c in block_cells if c > split_col}
        return (_subdivide_block(left, rng, lot_id_counter, min_w, min_d) +
                _subdivide_block(right, rng, lot_id_counter, min_w, min_d))

def generate_lots(grid, config, blocks, sink=None):
    yield GeneratorProgress(PHASE_LOTS, 0.0, 'Subdividing blocks into lots …')
    rng = random.Random(config.master_seed ^ SALT_LOTS)
    lot_id_counter = [0]
    all_lots = []

    for i, block in enumerate(blocks):
        if not block:
            continue
        sample_r, sample_c = next(iter(block))
        if grid[sample_r][sample_c].is_park:
            continue   # parks are not subdivided into lots

        lots = _subdivide_block(block, rng, lot_id_counter, LOT_MIN_WIDTH, LOT_MIN_DEPTH)
        for lid, lot_cells in lots:
            for r, c in lot_cells:
                grid[r][c].lot_id = lid
            all_lots.append(lot_cells)

        if i % 30 == 0:
            yield GeneratorProgress(PHASE_LOTS, i / max(len(blocks), 1),
                                    f'Lots: {lot_id_counter[0]} so far …')

    if sink is not None:
        sink.extend(all_lots)

    yield GeneratorProgress(PHASE_LOTS, 1.0,
                             f'Lot subdivision complete — {lot_id_counter[0]} lots.')
```

### Acceptance criteria
- `python main.py --no-render` outputs a `[LOTS        ]` phase line
- `generator.stats['lots']` contains an integer > 0
- Every non-road, non-water, non-park, non-exterior land cell has `lot_id >= 0`
- Park cells retain `lot_id == -1`
- Each lot is contiguous (connected set of cells) and rectangular (all cells share the same bounding box with no gaps for a simple rectangular block)
- Minimum lot area is 4 cells (2×2) — no lot smaller than this exists
- Same seed produces same lot distribution (deterministic)

---

## Unit 6 — Building Density Gradient

**Priority:** MED
**Files to modify:**
- `map_builder/map_state.py` — add `density_score: float = 0.0` field to `MapCell`
- `map_builder/phases/zones.py` — extend `generate_zones()` to compute density_score after zone assignment
- `app.py` — visualize density score as brightness modulation on land cells
**New files to create:** None
**Estimated LOC:** 80
**Dependencies:** Unit 1 (zones must be merged); Unit 3 recommended (density is most useful per-block, but works per-cell too)

### What to implement
- In `map_state.py`, add to `MapCell`:
  - `density_score: float = 0.0` — 0.0 = low density (rural edge), 1.0 = high density (CBD next to highway)
- In `zones.py`, after the zone assignment loop, add a second pass:
  - Collect highway cell set: `hw_cells = {(r, c) for r, c, cell in grid.all_cells() if cell.is_road and cell.road_category == ROAD_HIGHWAY}`
    - **Note:** highways are assigned in Phase 2 which runs AFTER zones. Therefore density_score cannot use highway proximity during the zones phase. Instead, move the density computation to a new method or extend the connector phase. The safest approach: compute density_score in a new helper `compute_density_scores(grid)` that runs at the END of `map_generator.generate()` after all road phases, and is called as a post-pass (not a generator phase — just a blocking call, ~5ms on 96×72 maps).
  - For each land cell:
    - `base` = `{ZONE_CBD: 0.85, ZONE_MIDTOWN: 0.55, ZONE_RESIDENTIAL: 0.25}[cell.zone_id]`
    - `hw_dist` = Chebyshev distance to nearest highway cell (cap at 20)
    - `hw_bonus` = `max(0.0, 0.15 * (1.0 - hw_dist / 10.0))`
    - `density_score = clamp(base + hw_bonus, 0.0, 1.0)`
    - Write to `cell.density_score`
- In `map_generator.py`:
  - Add a call to `_compute_density_post_pass(self.grid)` after the generator's yield-from chain (before the final stats computation)
  - This is NOT a generator — it is a blocking one-pass function call
- In `app.py`:
  - When `_zone_mode` is True, modulate land cell brightness by `density_score`:
    - Base color = zone color (from Unit 2)
    - Darkened: `r = int(base_r * (0.5 + 0.5 * cell.density_score))` for each channel
    - Dense blocks (density ~1.0) render at full zone color; sparse blocks (density ~0.1) render at 50% brightness
  - This makes high-density areas visually pop within each zone band

### Algorithm
```python
# In map_generator.py, add after all yield from calls:

def _compute_density_post_pass(grid: MapGrid) -> None:
    from .constants import ROAD_HIGHWAY, ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL
    # Collect highway cells for distance lookup
    hw_cells = [
        (r, c) for r, c, cell in grid.all_cells()
        if cell.is_road and cell.road_category == ROAD_HIGHWAY
    ]
    ZONE_BASE = {ZONE_CBD: 0.85, ZONE_MIDTOWN: 0.55, ZONE_RESIDENTIAL: 0.25}

    for r, c, cell in grid.all_cells():
        if not cell.is_land:
            continue
        base = ZONE_BASE.get(cell.zone_id, 0.25)
        if hw_cells:
            # Chebyshev distance (fast approximation using max of abs diffs)
            min_dist = min(max(abs(r - hr), abs(c - hc)) for hr, hc in hw_cells)
        else:
            min_dist = 20
        hw_bonus = max(0.0, 0.15 * (1.0 - min(min_dist, 10) / 10.0))
        cell.density_score = min(1.0, max(0.0, base + hw_bonus))

# In app.py, update cell_color():
    if cell.is_land:
        if getattr(cell, 'is_park', False):
            return C_PARK
        if _zone_mode:
            base = {
                ZONE_CBD:         C_LAND_CBD,
                ZONE_MIDTOWN:     C_LAND_MIDTOWN,
                ZONE_RESIDENTIAL: C_LAND_RESIDENTIAL,
            }.get(cell.zone_id, C_LAND)
            # modulate brightness by density_score
            factor = 0.5 + 0.5 * getattr(cell, 'density_score', 0.5)
            return tuple(int(ch * factor) for ch in base)
        return C_LAND
```

**Performance note:** The Chebyshev distance loop over all land cells × all highway cells is O(land × hw). On a 96×72 = 6912 cell map with ~200 highway cells, this is ~1.4M comparisons — acceptable (< 50ms). If map size grows > 200×200, replace with a BFS distance map.

### Acceptance criteria
- `MapCell` has a `density_score` attribute with a float value between 0.0 and 1.0
- CBD cells adjacent to a highway have `density_score > 0.85`
- Residential cells far from any highway have `density_score < 0.35`
- In `app.py` with zone mode on, CBD-near-highway areas appear brighter than CBD-far-from-highway areas
- Residential outer edge appears noticeably darker/dimmer than CBD center in zone mode
- Generation time increase (measured via `stats['elapsed_s']`) is less than 100ms on 96×72 maps

---

## Unit 7 — Zone Character Overlay in `main.py`

**Priority:** LOW
**Files to modify:** `main.py` only
**New files to create:** None
**Estimated LOC:** 35
**Dependencies:** Unit 1 (zones must exist on cells)

### What to implement
- Add a `--zones` flag to `parse_args()` (action='store_true', default False)
- Modify `render_ascii()` to accept an optional `zone_mode: bool = False` parameter
- When `zone_mode` is True, in the `elif cell.is_land:` branch:
  - `ZONE_CBD` → use character `'·'` with ANSI color code `\033[0;33m` (dim yellow = warm urban)
  - `ZONE_MIDTOWN` → use character `','` with ANSI color code `\033[0;32m` (dim green = mixed)
  - `ZONE_RESIDENTIAL` → use character `'.'` with ANSI color code `\033[0;32m` (same green, darker)
  - Default → existing `'.'` with no color
- Pass `zone_mode=args.zones` when calling `render_ascii(generator.grid)` in `main()`
- Update the legend print at the bottom of `main()` to include zone character legend when `--zones` is active:
  - `· CBD (yellow)   , Midtown (green)   . Residential`
- Import `ZONE_CBD`, `ZONE_MIDTOWN`, `ZONE_RESIDENTIAL` from `map_builder.constants` at top

### Algorithm
```python
# parse_args addition:
p.add_argument('--zones', action='store_true', help='Show zone overlay in ASCII render')

# render_ascii signature update:
def render_ascii(grid, zone_mode: bool = False) -> str:
    ...
    elif cell.is_land:
        if zone_mode:
            if cell.zone_id == ZONE_CBD:
                line.append('\033[0;33m·\033[0m')
            elif cell.zone_id == ZONE_MIDTOWN:
                line.append('\033[0;32m,\033[0m')
            else:
                line.append('.')
        else:
            line.append('.')
    ...

# main() call update:
print(render_ascii(generator.grid, zone_mode=args.zones))

# Legend update (conditional):
if args.zones:
    print('Zone legend:  \033[0;33m· CBD\033[0m   \033[0;32m, Midtown\033[0m   . Residential')
```

### Acceptance criteria
- `python main.py --zones` renders `·` characters in the CBD ring, `,` in midtown, `.` in residential
- `python main.py` (without `--zones`) renders identically to before this change
- Colors are visible in a terminal that supports ANSI escape codes (Windows Terminal, VSCode terminal)
- `--zones --no-render` suppresses the zone render correctly

---

## Unit 8 — CBD Civic Anchor

**Priority:** MED
**Files to modify:**
- `map_builder/constants.py` — add `CIVIC_ANCHOR_RADIUS`, `PHASE_CIVIC` constants
- `map_builder/map_state.py` — add `is_civic_anchor: bool = False` to `MapCell`
- `map_builder/map_generator.py` — add `_run_phase_civic_anchor()` call after zones, before highways
- `app.py` — add distinctive render color for civic anchor cell
**New files to create:**
- `map_builder/phases/civic.py`
**Estimated LOC:** 65
**Dependencies:** Unit 1 (zones must be present)

### What to implement
- After zone assignment, find the Chebyshev centroid of all `ZONE_CBD` land cells:
  - `center_r = mean of r for all CBD land cells`
  - `center_c = mean of c for all CBD land cells`
  - Find the actual land cell closest to `(center_r, center_c)` in Chebyshev distance
  - Mark that cell as `is_civic_anchor = True`
- Store `self.civic_anchor: tuple[int, int] | None = None` in `MapGenerator`
- In `app.py`, add `C_CIVIC = (255, 80, 80)` (bright red) and render civic anchor cell as this color when `_zone_mode` is True (or always — it is a single cell)
- In `main.py`, render the civic anchor cell as `'\033[1;31m★\033[0m'` (bold red star)

### Algorithm
```python
# civic.py
from ..constants import PHASE_CIVIC, ZONE_CBD
from ..map_state import MapGrid, MapConfig, GeneratorProgress

PHASE_CIVIC: Final[str] = 'civic'  # add to constants.py

def generate_civic_anchor(grid, config, sink=None):
    yield GeneratorProgress(PHASE_CIVIC, 0.0, 'Placing civic anchor …')
    cbd_cells = [(r, c) for r, c, cell in grid.all_cells()
                 if cell.is_land and cell.zone_id == ZONE_CBD]
    if not cbd_cells:
        yield GeneratorProgress(PHASE_CIVIC, 1.0, 'No CBD cells — civic anchor skipped.')
        return
    mean_r = sum(r for r, c in cbd_cells) / len(cbd_cells)
    mean_c = sum(c for r, c in cbd_cells) / len(cbd_cells)
    best = min(cbd_cells, key=lambda rc: max(abs(rc[0] - mean_r), abs(rc[1] - mean_c)))
    grid[best[0]][best[1]].is_civic_anchor = True
    if sink is not None:
        sink.append(best)
    yield GeneratorProgress(PHASE_CIVIC, 1.0,
                             f'Civic anchor placed at {best}.')
```

### Acceptance criteria
- Exactly one cell has `is_civic_anchor = True` after generation
- That cell is always a land cell in the CBD zone
- In `app.py`, the civic anchor cell renders as a distinct bright color (distinguishable from surrounding CBD land)
- In `main.py --zones`, the civic anchor cell renders as `★`
- Regenerating with the same seed always places the anchor at the same cell

---

## Unit 9 — Noise-Offset Connector Spacing (Irregular Blocks)

**Priority:** LOW
**Files to modify:** `map_builder/phases/connector.py` only
**New files to create:** None
**Estimated LOC:** 25
**Dependencies:** Unit 1

### What to implement
- In `connector.py`, after computing `ns_bases` and `ew_bases` (the raw list of street column/row positions), add a noise jitter step before the zone-aware density filter
- For each position in `ns_bases`, apply: `base_col = base_col + int(noise2d(...) * av_block * 0.25)` clamped to map bounds, ensuring no two avenues end up on the same column
- For each position in `ew_bases`, apply: `base_row = base_row + int(noise2d(...) * cs_block * 0.25)` clamped to map bounds
- Use the existing `perm` table and a distinct noise coordinate (`base_col / cols * 3.0, 0.5`) to avoid correlating with existing noise
- After applying jitter, re-sort and de-duplicate the positions (clamp to unique values with minimum separation of `min_block_depth + 1`)
- This produces 10-20% size variance in block dimensions without breaking the overall grid structure

### Algorithm
```python
# After ns_bases is computed (list(range(av_block, cols - av_block//2, av_block))):
ns_bases_jittered = []
seen_cols = set()
for base_col in ns_bases:
    jitter = int(noise2d(base_col / cols * 3.0, 0.5, perm) * av_block * 0.25)
    jittered = max(2, min(cols - 2, base_col + jitter))
    if jittered not in seen_cols:
        ns_bases_jittered.append(jittered)
        seen_cols.add(jittered)
ns_bases = sorted(ns_bases_jittered)

# Same pattern for ew_bases using cs_block and row coordinates.
```

### Acceptance criteria
- Street grid still covers the full map (no huge empty gaps larger than 2× intended spacing)
- Block widths vary measurably across the map (not all equal to `av_block`)
- Variance in N-S block width: standard deviation > 1.5 cells and < `av_block * 0.4` cells (not too uniform, not too chaotic)
- Same seed still produces the same layout (deterministic — noise is seed-derived)
- `python main.py --no-render` completes without error

---

## Section 3: Priority Order for Team 4

Execute in this sequence. Units marked **(parallel)** can be run simultaneously if multiple agents are available.

```
Phase A — Foundation (must be serial):
  1. Unit 1 — Branch merge (prerequisite for everything)

Phase B — Visual + Structural core (parallel after Unit 1):
  2a. Unit 2 — Zone colors in app.py          [parallel with 2b, 2c]
  2b. Unit 3 — Block detection phase          [parallel with 2a, 2c]
  2c. Unit 7 — Zone chars in main.py          [parallel with 2a, 2b]

Phase C — Block-dependent features (serial after Unit 3):
  3.  Unit 4 — Park placement                 [depends on Unit 3]
  4.  Unit 5 — Lot subdivision markers        [depends on Units 3 + 4]

Phase D — Enhancement (parallel after Phase B):
  5a. Unit 6 — Density gradient               [parallel with 5b; depends on Unit 1]
  5b. Unit 8 — CBD civic anchor               [parallel with 5a; depends on Unit 1]
  5c. Unit 9 — Noise-offset connector spacing [parallel with 5a, 5b; depends on Unit 1]
```

**Dependency matrix:**
- Unit 1 → all others
- Unit 3 → Units 4, 5
- Unit 4 → Unit 5
- Units 2, 6, 7, 8, 9 are independent of each other (edit disjoint files)

**File conflict warning:** Units 2 and 6 both modify `app.py`. Assign to the same agent or serialize them. Units 3, 4, 5 all modify `constants.py` and `map_state.py` — serialize these or merge carefully.

---

## Section 4: E2E Verification Checklist (for Team 5)

The following items must all pass after Team 4 completes all units. Test against seed=1 and seed=42 unless otherwise noted.

1. **Branch merge integrity:** `git log --oneline map-design | head -5` contains commits from both the initial commit and the city realism overhaul. `git diff main map-design --stat` shows the phases/zones.py and cul-de-sac additions.

2. **Pipeline completion:** `python main.py --no-render --seed 1` exits with code 0 and prints phase headers: COASTLINE, ZONES, HIGHWAY, CONNECTOR, SIDEWALK, BLOCKS, PARKS, LOTS, COMPLETE. All nine phase headers present.

3. **Determinism:** Run `python main.py --no-render --seed 42` twice. Both runs print identical elapsed times within 10% and identical stats (land, water, roads, sidewalks, blocks, parks, lots counts all identical).

4. **Zone mode toggle:** Launch `python app.py --seed 1`. Press `Z`. Verify the land area changes from uniform tan to a visible three-color band (warm center, greenish outer). Press `Z` again. Land reverts to uniform tan. No crash, no error.

5. **Zone color correctness:** With zone mode on, the center of the map (CBD) shows `C_LAND_CBD = (196,168,130)` approximate color. The outer ring shows `C_LAND_RESIDENTIAL = (122,158,110)` approximate color. The color bands are concentric (not random noise).

6. **Park rendering:** With zone mode on, some land cells appear in a distinct green `C_PARK = (72,140,72)`. These cells should cluster in small pockets (CBD small blocks) and scattered medium patches (Residential). No road, water, or sidewalk cell is park-colored.

7. **Density gradient visible:** With zone mode on, CBD cells adjacent to gold highway cells are noticeably brighter than CBD cells far from highways. Outer residential cells are noticeably dimmer than inner CBD cells.

8. **Civic anchor visible:** With zone mode on (or always), exactly one cell in the CBD area renders in the distinct civic anchor color `C_CIVIC = (255,80,80)`. Only one such cell exists per map.

9. **Zone ASCII overlay:** `python main.py --zones --seed 1` renders `·` (dot) characters in the center CBD area, `,` characters in the midtown ring, and `.` in the outer residential zone. The ASCII pattern matches the visual Pygame pattern.

10. **Block detection count:** `generator.stats['blocks']` for seed=1 on a 96×72 map is greater than 0 and less than 500 (sanity bounds; actual value will be ~50-200 depending on connector density). No cell in the interior has `block_id == -1` unless it is a road cell or an exterior (edge-touching) region.

11. **Park count plausibility:** `generator.stats['parks']` for seed=1 is between 5 and 60. Specifically: at least one park exists in the CBD zone (small block rule), and at least one in Residential zone (probabilistic rule with p=0.25).

12. **Lot count plausibility:** `generator.stats['lots']` for seed=1 is greater than `generator.stats['blocks']` (each block subdivides into at least 1 lot; most split into 2+). Every non-road, non-water, non-park, non-exterior land cell has `lot_id >= 0`.

13. **Block spacing variation:** Running `python main.py --no-render --seed 1` and `--seed 2`: the block counts differ (seed-dependent variance from noise-jittered connector spacing in Unit 9). The difference should be non-zero.

14. **No new dependencies:** `python -c "import map_builder"` succeeds with only the standard library plus pygame (already required). No `pip install` of any new package is needed.

15. **Key hints updated:** In the Pygame HUD, the key hint strip at the bottom right contains `Z zone`. Pressing `Z` is the only action that triggers the zone color mode — no other key accidentally triggers it.

16. **HUD legend updates:** When zone mode is active, the HUD legend swatches show `CBD`, `midtown`, `residential` labels instead of the single `land` label. When zone mode is off, the single `land` swatch is shown.

17. **No regression on existing features:** Highways still render gold. Connectors still render cyan. Roundabouts still render (green circle in main.py). Cul-de-sac stubs still appear in residential zones. Sidewalks still render grey. The `SPACE`, `R`, `H`, `1-9`, `+/-`, arrow keys all still function as documented in app.py's header comment.

18. **Backwards compatibility of MapCell:** A `MapCell()` constructed with no arguments still works (all new fields have defaults: `block_id=-1`, `lot_id=-1`, `density_score=0.0`, `is_park=False`, `is_civic_anchor=False`). No `TypeError` on construction.

19. **`generate_blocking()` still works:** `generator.generate_blocking()` (used in map_generator tests) completes without error with all new phases wired in.

20. **Performance regression check:** `stats['elapsed_s']` for seed=1 on a 96×72 map is under 5.0 seconds on the development machine. The density gradient post-pass (Unit 6) and block detection (Unit 3) do not cause a timeout-scale regression.

---

*Plan produced by Team 3 (Senior Development Bridge). All unit estimates, algorithms, and acceptance criteria are derived from the Team 1 city planning report, Team 2 algorithm research report, and direct analysis of the `claude/hopeful-babbage-ad0877` codebase.*
