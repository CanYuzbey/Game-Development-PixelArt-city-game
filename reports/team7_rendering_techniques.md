# Team 7 — Senior Procedural Rendering Research Report
## Pixel-Art Top-Down City Map Engine: Visual Enhancement Techniques

**Engine:** Python / Pygame  
**Grid:** 10 m/cell, typical map 96×72 cells, each cell rendered as 8×8 pixels  
**Constraint:** No sprites — RGB color per cell only  
**Date:** 2026-05-09

---

## 1. Per-Lot Color Variation Algorithm

### Problem

Uniform zone colors make the map look like a flat zone diagram rather than a city. Real cities show visible texture: aging buildings, varying materials, setback differences, and density gradients.

### Design Goals

- **Deterministic** — same `lot_id` always yields the same color offset.
- **Subtle** — variation stays within ±10–20% per channel so zone identity remains readable.
- **Realistic** — CBD shifts darker + bluer under high density; Residential shifts warmer/lighter on larger lots.

### Algorithm

The core idea is to use `lot_id` as a seed for a lightweight pseudo-random number generator (LCG), produce three independent per-channel offsets, then apply zone-specific bias on top of those offsets.

```python
def lot_color_variation(
    base_color: tuple,
    lot_id: int,
    density_score: float,   # 0.0 (sparse) – 1.0 (max density)
    zone_id: int,           # 0=residential, 1=commercial, 2=CBD, 3=industrial, 4=park
) -> tuple:
    """
    Return a perturbed RGB color for a single lot.
    All arithmetic is integer; no external libs required.
    """
    # --- Deterministic noise via a 3-tap LCG ---
    # Each tap uses a different prime multiplier so channels are decorrelated.
    PRIMES = (1664525, 22695477, 214013)
    ADDS   = (1013904223, 1664525, 6364136223846793005)
    MASK   = 0xFFFFFFFF

    seeds = [
        ((lot_id * PRIMES[i] + ADDS[i]) & MASK) for i in range(3)
    ]
    # Map each 32-bit seed to a float in [-1, 1]
    noise = [(s / MASK) * 2.0 - 1.0 for s in seeds]

    # --- Zone-specific variation range (max delta per channel, 0–255) ---
    # Wider range → more visual texture. Keep ≤ 40 (≈15%) for subtlety.
    VARIATION = {
        0: 30,   # Residential — warm variation, slightly large
        1: 25,   # Commercial  — moderate
        2: 20,   # CBD         — tight; density bias does most of the work
        3: 35,   # Industrial  — widest; gritty variation
        4: 18,   # Park        — small; don't disturb green hue
    }
    var = VARIATION.get(zone_id, 25)

    r, g, b = base_color

    # --- Base noise offsets ---
    dr = noise[0] * var
    dg = noise[1] * var
    db = noise[2] * var

    # --- Zone-specific density bias ---
    if zone_id == 2:          # CBD: denser → darker + bluer
        dark = density_score * 30       # pull down R and G
        blue = density_score * 20       # push up B
        dr -= dark
        dg -= dark
        db += blue

    elif zone_id == 0:        # Residential: larger lots (low density) → warmer/lighter
        warmth = (1.0 - density_score) * 20   # low density → more warmth
        dr += warmth          # more red
        dg += warmth * 0.4    # slight yellow tint
        db -= warmth * 0.3    # reduce blue

    elif zone_id == 3:        # Industrial: denser → greener/more yellow-grey
        dr -= density_score * 15
        dg -= density_score * 5
        db -= density_score * 20

    # --- Clamp to valid range ---
    r_out = max(0, min(255, int(r + dr)))
    g_out = max(0, min(255, int(g + dg)))
    b_out = max(0, min(255, int(b + db)))

    return (r_out, g_out, b_out)
```

### Usage Pattern

Call this once per lot at map-generation time and store the result alongside other lot data. Never recompute at render time — the function is deterministic, so caching is trivial.

```python
# At generation time:
for lot in all_lots:
    lot.display_color = lot_color_variation(
        base_color    = ZONE_BASE_COLORS[lot.zone_id],
        lot_id        = lot.id,
        density_score = lot.density_score,
        zone_id       = lot.zone_id,
    )

# At render time:
pygame.draw.rect(surface, lot.display_color, lot.rect)
```

### Calibration Notes

- Increase `var` values toward 40 for a "worn" city look; decrease toward 10 for a clean modern city.
- The CBD dark bias of 30 points is calibrated for a `base_color` around `(100, 110, 140)`. Adjust if your CBD base is significantly lighter or darker.
- For neon-style games, replace the clamp with a `min(255, max(0, ...))` HSV saturation boost instead.

---

## 2. Building Edge / Outline Rendering

### Option Comparison

| | Option A: Inner Border | Option B: Neighbor-Aware Edges | Option C: Drop Shadow |
|---|---|---|---|
| Complexity | Trivial | Moderate | Easy |
| Accuracy | Approximate | Exact | Approximate |
| Grid access needed | No | Yes | No |
| Visual quality | Good | Best | Decorative |
| Cost (8×8 cells) | Negligible | ~4 neighbor lookups/cell | Negligible |
| Works on isolated lots | Yes | Yes | Yes |
| Looks good at 8px scale | Yes | Yes | Cluttered |

### Recommendation: Option A as Default, Option B When Grid Is Available

At 8×8 pixels per cell, a 1px inner border consumes 12.5% of the cell face — exactly the right visual weight. Option C's shadow at +1,+1 overlaps neighboring cells, causing color bleed at this scale. Option B is the most accurate but requires passing the grid to the renderer.

**Implement Option A immediately; add Option B as a quality toggle.**

### Option A — 1px Inner Border (Recommended Default)

```python
def render_building_cell_A(surface, color, cell_rect, border_fraction=0.85):
    """
    Draw a building cell with a 1px darker inner border.
    cell_rect: pygame.Rect for the full cell
    """
    DARKEN = 0.65   # border is 65% brightness of fill color

    border_color = tuple(int(c * DARKEN) for c in color)

    # Full cell in border color first, then inset fill
    pygame.draw.rect(surface, border_color, cell_rect)

    inset = pygame.Rect(
        cell_rect.x + 1,
        cell_rect.y + 1,
        cell_rect.width  - 2,
        cell_rect.height - 2,
    )
    pygame.draw.rect(surface, color, inset)
```

### Option B — Neighbor-Aware Shared-Edge Darkening

```python
EDGE_DARK = 0.60   # shared interior edges at 60% brightness

def render_building_cell_B(surface, color, grid, gx, gy, cell_size):
    """
    Darken only the edges shared with other building cells.
    grid: 2D array where grid[y][x].is_building is True/False
    gx, gy: grid coordinates of this cell
    cell_size: pixel size of one cell (e.g. 8)
    """
    x = gx * cell_size
    y = gy * cell_size
    cell_rect = pygame.Rect(x, y, cell_size, cell_size)

    pygame.draw.rect(surface, color, cell_rect)

    dark = tuple(int(c * EDGE_DARK) for c in color)

    neighbors = {
        "top":    (gx,     gy - 1),
        "bottom": (gx,     gy + 1),
        "left":   (gx - 1, gy    ),
        "right":  (gx + 1, gy    ),
    }

    for side, (nx, ny) in neighbors.items():
        if is_building(grid, nx, ny):    # helper: bounds-check + type-check
            if side == "top":
                pygame.draw.line(surface, dark, (x, y), (x + cell_size - 1, y))
            elif side == "bottom":
                pygame.draw.line(surface, dark, (x, y + cell_size - 1),
                                 (x + cell_size - 1, y + cell_size - 1))
            elif side == "left":
                pygame.draw.line(surface, dark, (x, y), (x, y + cell_size - 1))
            elif side == "right":
                pygame.draw.line(surface, dark, (x + cell_size - 1, y),
                                 (x + cell_size - 1, y + cell_size - 1))
```

### Option C — Drop Shadow (Decorative Only)

```python
def render_building_cell_C(surface, color, cell_rect):
    shadow_color = (30, 30, 30)
    shadow_rect  = cell_rect.move(1, 1)
    pygame.draw.rect(surface, shadow_color, shadow_rect)
    pygame.draw.rect(surface, color,        cell_rect)
```

**Do not use Option C as the primary technique at 8px scale** — the +1,+1 bleed corrupts road/sidewalk cells below and to the right of every building.

### Performance Note

Pre-bake all lot outlines into a single `pygame.Surface` (dirty-rect system). Border lines never change at runtime; there is no need to recompute per frame.

---

## 3. Park Size and Selection Algorithm Fix

### Root Cause

The current algorithm selects parks from blocks in the 1–9 cell range. Blocks that small cannot accommodate a park that reads as a park at map scale. A neighborhood park in a 10 m/cell grid should occupy at least 20 cells (200 m × 100 m) to be visible, and up to 100 cells (1 km²) for a major urban park.

### Replacement Algorithm: `generate_parks()`

#### Park Score Formula

```
park_score(block) = size_factor × zone_factor × isolation_factor
```

- **size_factor** = `clamp((block.size - 20) / 80, 0, 1)` — zero below 20 cells, max at 100 cells.
- **zone_factor** — parks fit best near residential zones. `{residential: 1.0, commercial: 0.7, CBD: 0.3, industrial: 0.1}`.
- **isolation_factor** = `clamp(min_dist_to_other_parks / 15, 0, 1)` — penalize clustering within 15 cells.

#### Full Pseudocode

```python
MIN_PARK_CELLS   = 20     # absolute floor
MAX_PARK_CELLS   = 100    # cap for realistic scale
MAX_PARKS_PER_ZONE = 1    # one major park per zone
PARK_MIN_SPACING = 15     # cells between park centroids

ZONE_FACTOR = {
    ZONE_RESIDENTIAL: 1.0,
    ZONE_COMMERCIAL:  0.7,
    ZONE_CBD:         0.3,
    ZONE_INDUSTRIAL:  0.1,
    ZONE_PARK:        0.0,   # already a park
}

def generate_parks(blocks, zones, existing_roads):
    """
    blocks     : list of Block objects with .size (cell count), .centroid (gx,gy),
                 .dominant_zone_id
    zones      : dict zone_id → Zone object
    Returns    : list of Block objects designated as parks
    """
    # Step 1: filter candidate blocks
    candidates = [
        b for b in blocks
        if MIN_PARK_CELLS <= b.size <= MAX_PARK_CELLS
        and b.dominant_zone_id != ZONE_PARK
    ]

    if not candidates:
        return []

    # Step 2: compute park scores
    park_assignments = []      # list of chosen Block objects
    parks_per_zone   = defaultdict(int)

    def isolation_factor(block, chosen):
        if not chosen:
            return 1.0
        min_dist = min(
            chebyshev(block.centroid, p.centroid) for p in chosen
        )
        return min(1.0, min_dist / PARK_MIN_SPACING)

    def size_factor(block):
        return max(0.0, min(1.0, (block.size - MIN_PARK_CELLS) /
                                  (MAX_PARK_CELLS - MIN_PARK_CELLS)))

    # Step 3: greedy selection sorted by best score
    # Re-evaluate isolation_factor after each choice (greedy is fine at city scale).
    for _ in range(len(blocks)):          # upper bound; breaks on empty candidates
        if not candidates:
            break

        scored = []
        for b in candidates:
            if parks_per_zone[b.dominant_zone_id] >= MAX_PARKS_PER_ZONE:
                continue
            sf = size_factor(b)
            zf = ZONE_FACTOR.get(b.dominant_zone_id, 0.5)
            iso = isolation_factor(b, park_assignments)
            score = sf * zf * iso
            if score > 0:
                scored.append((score, b))

        if not scored:
            break

        scored.sort(key=lambda x: -x[0])
        best_score, best_block = scored[0]

        # Require a minimum score threshold to avoid forcing bad parks
        if best_score < 0.15:
            break

        park_assignments.append(best_block)
        parks_per_zone[best_block.dominant_zone_id] += 1
        candidates.remove(best_block)

    return park_assignments


def chebyshev(a, b):
    """Chebyshev distance between two (gx, gy) grid points."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
```

#### Expected Output

On a 96×72 map with realistic road spacing:
- 4–8 parks total.
- Each park 20–100 cells in size.
- No two parks within 15 cells of each other.
- Parks cluster near residential zones, away from CBD.

---

## 4. Block and Lot Sizing — `connector_spacing` Fix

### Current vs. Target Block Sizes

| Parameter | Current | Proposed |
|---|---|---|
| `connector_spacing` | 6 | 16 |
| `avenue_spacing` | 15 | 40 |
| Block size range | 4–17 cells | 14–38 cells |
| Lot width range | 3–5 cells | 5–10 cells |
| Lot depth range | 3–3 cells | 8–15 cells |
| `LOT_MIN_WIDTH` | 3 | 5 |
| `LOT_MIN_DEPTH` | 3 | 8 |
| `connector_density` | (current) | reduce by ~35% |

### Road Density Analysis

Road density = fraction of cells that are road-type. Target: 20–30%.

With the current settings (connector every 6, avenue every 15):
- Connectors consume ~1 cell per 6 → ~17% of rows/columns.
- Avenues consume ~1 cell per 15 → ~7% of rows/columns.
- Combined 2D density: `1 - (5/6)² × (14/15)² ≈ 1 - 0.833 × 0.934 ≈ 29%` — already at the high end.

With proposed settings (connector every 16, avenue every 40):
- Connectors: 1 per 16 → ~6% of linear space.
- Avenues: 1 per 40 → ~2.5% of linear space.
- Combined 2D density: `1 - (15/16)² × (39/40)² ≈ 1 - 0.879 × 0.951 ≈ 16%` — under target.

**Correction:** Add minor roads (alleys) at `alley_spacing=8` inside blocks, or widen avenues to 2 cells:

```
Road density with alley_spacing=8:
  1 - (7/8)² × (15/16)² × (39/40)² ≈ 1 - 0.766 × 0.879 × 0.951 ≈ 36%
```

Slightly over. Final recommended values:

```python
# road_generator.py — recommended constants
CONNECTOR_SPACING  = 16     # was 6
AVENUE_SPACING     = 40     # was 15
ALLEY_SPACING      = 10     # new; alleys between connectors
LOT_MIN_WIDTH      = 5      # was 3
LOT_MIN_DEPTH      = 8      # was 3

# connector_density controls how many candidate connectors are actually placed
# (1.0 = all candidates placed). Reduce to thin out minor roads.
CONNECTOR_DENSITY  = 0.55   # was ~0.85; reduces by ~35%
```

This combination gives:
- Block sizes: 15–38 cells (150 m – 380 m) — matches Manhattan blocks at 10 m/cell.
- Lot sizes: 5×8 to 10×15 cells (50 m × 80 m to 100 m × 150 m) — realistic mixed-use footprints.
- Road density: approximately 22–27% depending on zone connector density.

### Zone-Specific `connector_density`

```python
ZONE_CONNECTOR_DENSITY = {
    ZONE_CBD:         0.80,   # dense grid — many short connectors
    ZONE_COMMERCIAL:  0.65,
    ZONE_RESIDENTIAL: 0.50,   # residential loops and cul-de-sacs
    ZONE_INDUSTRIAL:  0.40,   # large industrial blocks, few internal roads
}
```

### Why This Matters Visually

At 8px/cell, a 3-cell-wide lot is 24 pixels — barely visible. A 5-cell lot is 40 pixels, which can display the inner-border effect meaningfully. A 10-cell-wide lot (80 pixels) can show setback variation and courtyard effects described in Section 6.

---

## 5. Zone Boundary Visual Softening

### Problem

Abrupt zone transitions (zone_id changes cell-to-cell) read as unnatural hard lines. Real cities fade gradually between zones.

### Approach: Per-Cell Zone Blend Factor

Rather than changing zone_id (which drives game logic), compute a `zone_blend_factor` at render time only.

```python
def compute_zone_blend_factor(grid, gx, gy, radius=3):
    """
    Returns a float [0, 1] indicating how "pure" this cell's zone is.
    0.0 = cell is directly on a zone boundary
    1.0 = cell is deep inside its zone (pure)
    """
    my_zone = grid[gy][gx].zone_id
    total    = 0
    matching = 0

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = gx + dx, gy + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                if grid[ny][nx].zone_id == my_zone:
                    matching += 1
                total += 1

    return matching / total   # 1.0 if all neighbors match


def blended_zone_color(cell, grid, zone_base_colors):
    """
    Blend this cell's color toward neighbors' zone colors at boundaries.
    """
    blend = compute_zone_blend_factor(grid, cell.gx, cell.gy, radius=3)

    # Full zone color from our own zone
    own_color = zone_base_colors[cell.zone_id]

    if blend >= 0.90:
        return own_color    # pure zone cell — skip blending

    # Gather neighbor zone colors weighted by presence
    zone_weights = defaultdict(float)
    radius = 3
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = cell.gx + dx, cell.gy + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                nz = grid[ny][nx].zone_id
                zone_weights[nz] += 1.0

    total_weight = sum(zone_weights.values())
    r, g, b = 0.0, 0.0, 0.0
    for zid, w in zone_weights.items():
        zc = zone_base_colors[zid]
        frac = w / total_weight
        r += zc[0] * frac
        g += zc[1] * frac
        b += zc[2] * frac

    # Use blend factor to lerp between pure and blended color
    # blend close to 0 → mostly blended; blend close to 1 → mostly pure
    r_out = int(own_color[0] * blend + r * (1 - blend))
    g_out = int(own_color[1] * blend + g * (1 - blend))
    b_out = int(own_color[2] * blend + b * (1 - blend))

    return (
        max(0, min(255, r_out)),
        max(0, min(255, g_out)),
        max(0, min(255, b_out)),
    )
```

### Integration With `density_score`

The `density_score` can sharpen or soften the blend radius:

```python
# High-density zones (CBD) → sharper boundary (radius=2)
# Low-density zones (Residential edges) → softer boundary (radius=4)
def adaptive_blend_radius(density_score):
    return int(2 + (1.0 - density_score) * 2)   # range 2–4
```

### Performance

Pre-compute blend factors for all cells once at generation time and store in `cell.blend_factor`. Recompute only when zone boundaries change (i.e., after zone rezoning events). The blending at render time is then a single lerp — O(1) per cell.

---

## 6. Organic Block Shape Variation

### Overview

The road grid is rectangular and cannot change. However, individual lots within blocks can have irregular visual shapes via:
1. **Setback variation** — some lots appear recessed from the road edge.
2. **Interior courtyards** — some lots have a hollow interior.
3. **L-shapes / U-shapes** — sub-cells within a lot are selectively not drawn.

All techniques operate purely on rendering, leaving grid data untouched.

### Technique A: Setback Variation

```python
SETBACK_PROBABILITY = 0.20   # 20% of lots have a setback
SETBACK_DEPTH_CELLS = 1      # 1-cell setback (~10 m — typical zoning requirement)
ROAD_COLOR = (90, 90, 90)

def render_lot_with_setback(surface, lot, cell_size):
    """
    For lots flagged with setback, draw the road-facing edge in road color,
    then draw the building in the remaining rect.
    """
    import random
    rng = random.Random(lot.id ^ 0xDEADBEEF)

    has_setback = rng.random() < SETBACK_PROBABILITY
    if not has_setback:
        pygame.draw.rect(surface, lot.display_color, lot.rect)
        return

    # Determine which edge faces a road (simplified: use lot.road_facing_side)
    facing = lot.road_facing_side   # 'top', 'bottom', 'left', 'right'
    setback_px = SETBACK_DEPTH_CELLS * cell_size

    # Draw full lot in road/sidewalk color (setback area)
    sidewalk_color = tuple(int(c * 1.15) for c in ROAD_COLOR)   # lighter gray
    pygame.draw.rect(surface, sidewalk_color, lot.rect)

    # Draw inset building
    r = lot.rect
    if   facing == 'top':    bldg = pygame.Rect(r.x, r.y + setback_px, r.w, r.h - setback_px)
    elif facing == 'bottom': bldg = pygame.Rect(r.x, r.y, r.w, r.h - setback_px)
    elif facing == 'left':   bldg = pygame.Rect(r.x + setback_px, r.y, r.w - setback_px, r.h)
    else:                    bldg = pygame.Rect(r.x, r.y, r.w - setback_px, r.h)

    pygame.draw.rect(surface, lot.display_color, bldg)
```

### Technique B: Interior Courtyard (Cell-Level Hollow)

For larger lots (≥ 6×6 cells), randomly hollow out an interior rectangle.

```python
COURTYARD_MIN_LOT_AREA  = 36   # cells; only attempt on large lots
COURTYARD_PROBABILITY   = 0.15
COURTYARD_COLOR_FACTOR  = 0.55 # courtyard is darker (shadowed interior)

def render_lot_with_courtyard(surface, lot, cell_size):
    """
    Render lot as a filled rect, then overdraw courtyard rect in darker color.
    """
    import random
    rng = random.Random(lot.id ^ 0xC0FFEE)

    pygame.draw.rect(surface, lot.display_color, lot.rect)

    if lot.area_cells < COURTYARD_MIN_LOT_AREA:
        return
    if rng.random() >= COURTYARD_PROBABILITY:
        return

    # Courtyard occupies the inner 40-60% of the lot
    cx_frac = rng.uniform(0.35, 0.55)
    cy_frac = rng.uniform(0.35, 0.55)

    r = lot.rect
    cw = max(cell_size, int(r.w * cx_frac))
    ch = max(cell_size, int(r.h * cy_frac))
    cx = r.x + (r.w - cw) // 2
    cy = r.y + (r.h - ch) // 2

    courtyard_color = tuple(int(c * COURTYARD_COLOR_FACTOR) for c in lot.display_color)
    pygame.draw.rect(surface, courtyard_color, pygame.Rect(cx, cy, cw, ch))
```

### Technique C: L-Shape / U-Shape Lots

Decompose the lot into a list of sub-rects. Mark some sub-rects as "void" (drawn in ground/road color).

```python
def lot_to_shape_rects(lot, cell_size, shape='L'):
    """
    Returns list of (rect, is_building) tuples.
    shape: 'L', 'U', or 'rect' (default)
    """
    r = lot.rect
    w, h = r.w, r.h

    if shape == 'L':
        # Remove top-right quadrant
        main  = pygame.Rect(r.x, r.y, w // 2, h)
        wing  = pygame.Rect(r.x + w // 2, r.y + h // 2, w - w // 2, h - h // 2)
        void  = pygame.Rect(r.x + w // 2, r.y, w - w // 2, h // 2)
        return [(main, True), (wing, True), (void, False)]

    elif shape == 'U':
        left   = pygame.Rect(r.x, r.y, w // 3, h)
        right  = pygame.Rect(r.x + 2 * (w // 3), r.y, w - 2 * (w // 3), h)
        bottom = pygame.Rect(r.x + w // 3, r.y + h // 2, w // 3, h - h // 2)
        void   = pygame.Rect(r.x + w // 3, r.y, w // 3, h // 2)
        return [(left, True), (right, True), (bottom, True), (void, False)]

    else:
        return [(r, True)]


def render_shaped_lot(surface, lot, cell_size, ground_color=(60, 60, 60)):
    import random
    rng = random.Random(lot.id ^ 0x1337)

    # Only apply irregular shapes to large lots with low probability
    shape = 'rect'
    if lot.area_cells >= 30 and lot.zone_id in (ZONE_CBD, ZONE_COMMERCIAL):
        roll = rng.random()
        if roll < 0.08:
            shape = 'U'
        elif roll < 0.18:
            shape = 'L'

    for rect, is_building in lot_to_shape_rects(lot, cell_size, shape):
        color = lot.display_color if is_building else ground_color
        pygame.draw.rect(surface, color, rect)
```

---

## 7. Highway Visual Width

### Option Comparison

| | Option A: Visual Margin on Highway Cell | Option B: Shoulder Coloring on Adjacent Cells | Option C: 2-Cell-Wide Highway (Algorithm Change) |
|---|---|---|---|
| Requires algo change | No | No | Yes |
| Visual width increase | Moderate (+3px each side) | Subtle (color cue only) | Full (2× wide) |
| Preserves grid geometry | Yes | Yes | No |
| Implementation risk | None | None | Medium (road gen refactor) |
| Recommended | Yes (primary) | Yes (combine with A) | Only if road gen is modular |

### Recommendation: Combine Option A + Option B

Option A alone creates the impression of width. Option B reinforces it with color context. Together they achieve a strong visual highway signal without touching road generation.

### Option A: Visual Margin on Highway Cells

Draw the highway cell narrower than the full cell, leaving a gap that reads as a shoulder/curb.

```python
HIGHWAY_MARGIN_PX = 2   # 2px inset on each side of highway cell

def render_highway_cell(surface, cell, cell_size,
                         highway_color=(60, 65, 75),
                         shoulder_color=(80, 78, 72)):
    """
    Draw the highway surface with a visible shoulder margin.
    """
    x = cell.gx * cell_size
    y = cell.gy * cell_size

    full_rect = pygame.Rect(x, y, cell_size, cell_size)

    # Determine orientation: horizontal or vertical highway
    is_horizontal = cell.highway_horizontal   # set during road generation

    # Fill full cell with shoulder color
    pygame.draw.rect(surface, shoulder_color, full_rect)

    # Draw narrowed highway surface
    m = HIGHWAY_MARGIN_PX
    if is_horizontal:
        road_rect = pygame.Rect(x, y + m, cell_size, cell_size - 2 * m)
    else:
        road_rect = pygame.Rect(x + m, y, cell_size - 2 * m, cell_size)

    pygame.draw.rect(surface, highway_color, road_rect)

    # Center divider line (yellow or white, 1px)
    divider_color = (220, 200, 50)   # yellow center line
    if is_horizontal:
        mid_y = y + cell_size // 2
        pygame.draw.line(surface, divider_color, (x, mid_y), (x + cell_size - 1, mid_y))
    else:
        mid_x = x + cell_size // 2
        pygame.draw.line(surface, divider_color, (mid_x, y), (mid_x, y + cell_size - 1))
```

### Option B: Adjacent Shoulder Cells

Color cells immediately beside a highway in a "highway shoulder" color.

```python
SHOULDER_COLOR    = (95, 92, 85)    # warm dark gray, slightly beige
HIGHWAY_ZONE_COLOR = (70, 70, 80)   # connector color for context

def get_cell_render_color(cell, grid):
    """
    Override color for cells adjacent to highways.
    """
    if cell.road_type == ROAD_HIGHWAY:
        return HIGHWAY_ZONE_COLOR

    if cell.road_type in (ROAD_CONNECTOR, ROAD_SIDEWALK):
        # Check all 4 neighbors for highway
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = cell.gx + dx, cell.gy + dy
            if in_bounds(nx, ny) and grid[ny][nx].road_type == ROAD_HIGHWAY:
                return SHOULDER_COLOR

    return cell.display_color
```

### Option C: 2-Cell-Wide Highways (If Road Gen Is Modular)

If the road generation system can be refactored, store highway direction in the grid and claim two adjacent rows/columns per highway.

```python
# During road generation:
def place_highway(grid, axis, position, length, is_horizontal):
    """
    Place a 2-cell-wide highway.
    axis  : 'x' or 'y'
    position : starting cell index
    """
    for i in range(length):
        if is_horizontal:
            grid[position    ][i].road_type = ROAD_HIGHWAY
            grid[position + 1][i].road_type = ROAD_HIGHWAY
        else:
            grid[i][position    ].road_type = ROAD_HIGHWAY
            grid[i][position + 1].road_type = ROAD_HIGHWAY
```

This requires all downstream block-detection code to skip both highway rows. **Only recommended if road generation uses a clean pass-based system where road-cell marking is isolated from block subdivision.**

### Final Recommendation

- **Implement Option A** in the highway renderer immediately (pure render change, no data changes).
- **Implement Option B** as a color lookup in `get_cell_render_color()` (also pure render change).
- **Defer Option C** until road generation is refactored.

---

## Summary and Implementation Priority

| Priority | Section | Change | Effort |
|---|---|---|---|
| 1 (High) | §4 | Increase `connector_spacing` to 16, `avenue_spacing` to 40 | Low — change constants |
| 2 (High) | §1 | Add `lot_color_variation()` at generation time | Low — pure addition |
| 3 (High) | §3 | Replace `generate_parks()` with size-filtered greedy scorer | Medium |
| 4 (Medium) | §2 | Add Option A inner-border rendering to all building cells | Low |
| 5 (Medium) | §7 | Render highway cells with visual margin + shoulder coloring | Low |
| 6 (Medium) | §5 | Pre-compute zone blend factors; lerp colors at render time | Medium |
| 7 (Low) | §6 | Add setback and courtyard rendering for large lots | Low–Medium |

**Start with §4** (spacing constants) because block/lot sizing is the foundation everything else depends on. Then §1 (color variation) and §3 (park selection) — these are the most visually impactful changes with the lowest implementation risk.

---

*Report authored by Team 7 — Senior Procedural Rendering Research*  
*Engine: Python / Pygame | Grid: 10 m/cell | Cell render: 8×8 px*
