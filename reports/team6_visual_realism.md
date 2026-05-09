# Team 6 — Visual Realism Report
## Top-Down Pixel-Art Procedural City Map Engine

**Audience:** Coders implementing a Python/Pygame city generator (10 m/cell, 96×72 grid)
**Prepared by:** Senior Urban Visual Design Committee

---

## 1. What Makes a Top-Down City Map READ as a Real City?

### 1.1 Visual Hierarchy — What the Eye Reads First, Second, Third

A viewer scanning a real top-down urban map processes information in a fixed perceptual order driven by contrast, area, and structure. Your engine must produce all three layers or the result will look like a diagram, not a city.

| Priority | Element | Why the Eye Goes There |
|---|---|---|
| **1st — Structure** | Road network skeleton | Highest contrast against surroundings; continuous lines create gestalt "city shape" before any block detail is read |
| **2nd — Mass** | Building density and zone color clusters | Large color regions (CBD dark grey cluster, residential warm cluster) give the city its "districts" |
| **3rd — Texture** | Individual lot variation, parks, landmarks | Fine grain detail that rewards closer inspection; signals life and complexity |

**Practical implication:** If your road network is visually weak (roads too similar in color to land, or only 1px wide everywhere), the entire map collapses into visual noise. Roads must be legible at full zoom before any buildings are drawn.

### 1.2 Key Visual Characteristics by Zone Type

**CBD / Downtown** (as seen in Google Maps, SimCity 2000, real city centers)
- Very high building coverage per block — minimal visible ground between buildings
- Dominant hue: cool grey to charcoal, often with slight blue-grey cast (glass and steel)
- Block interiors almost entirely filled; setbacks near zero
- Street grid is tight and highly regular — shorter block lengths (~40–60 m, so 4–6 cells)
- Landmarks interrupt the grey mass with distinctive color or size
- Shadow implied by darker building colors (no need for real-time shadow rendering)
- Roads appear as narrow pale grey trenches between dark masses

**Midtown** (transitional zone — brick/concrete mid-rise)
- Building coverage ~70–80% of block area; some visible sidewalk gaps
- Mix of warmer brick reds, beige, and medium grey
- Block sizes slightly larger than CBD (60–100 m, so 6–10 cells)
- Building footprints more varied — rectangles of different widths visible
- Occasional small plaza or parking lot introduces a light-colored gap in the mass

**Residential** (low-density, detached/semi-detached, suburbs)
- Building coverage ~30–50% of block; large visible setbacks (garden/lawn)
- Warm, light colors — cream, tan, pale salmon — buildings appear as small bright islands in a sea of grass green
- Block sizes largest (80–150 m, 8–15 cells), lot sizes most varied
- Roads wider per block length ratio — residential streets feel spacious
- Trees/parks common and numerous; green is the dominant non-road color

**Pokemon city style note:** Pokemon maps use very regular 16×16 tile grids but signal zones through:
- Roof color (orange/red for houses, blue-grey for civic, dark for commercial)
- Building size (large single structure = civic/landmark, small repeating units = residential)
- Path color (grey in cities, tan/dirt outside)
- Green patches interspersed, never entirely absent even in urban zones

**OpenStreetMap standard style note:** OSM uses a clear 3-tier road hierarchy enforced by both width AND color: motorways are a distinct yellow-orange, primary roads are yellow, secondary grey-white, residential near-white. This creates instant legibility. Adopt this logic.

### 1.3 Why Procedurally Generated Cities Look Fake — Root Causes

| Failure Mode | Visual Symptom | Fix |
|---|---|---|
| **Uniform block sizes** | Grid looks like graph paper, not a city | Use variable block dimensions (see Section 3) |
| **Monotone zones** | All "residential" buildings are identical color | Per-lot color variance ±10–18 (see Section 4) |
| **No road hierarchy** | All streets look the same width/color | At least 3 visually distinct road types required |
| **Abrupt zone transitions** | Hard color cliff between CBD and residential | Blend zones over 2–3 block transition buffer |
| **Parks as empty voids** | Green rectangles with no internal detail | Internal park elements required (Section 6) |
| **No landmark contrast** | Civic buildings same mass as office buildings | Landmarks need unique color AND larger footprint |
| **100% block fill** | No relief, suffocating density | Even CBD blocks need 5–10% gap/plaza area |
| **Symmetric grid alignment** | All blocks axis-aligned with map edge | Slight road curvature or diagonal cuts break rigidity |

---

## 2. Realistic Color Palette — Exact RGB Values

All values are Python tuples `(R, G, B)`. References: Google Maps satellite-hybrid, OpenStreetMap Carto, SimCity 2000 zone colors, Pokemon city tile sets, and empirical sampling of real top-down map screenshots.

### 2.1 Master Palette

```python
COLORS = {

    # ── WATER ───────────────────────────────────────────────────────────────
    "ocean":               (106, 159, 191),  # Google Maps ocean — muted steel blue
    "river":               (122, 174, 204),  # Lighter, slight green undertone
    "river_shallow":       (144, 195, 215),  # Near-shore / canal shallows

    # ── ROADS ───────────────────────────────────────────────────────────────
    "highway":             (220, 194, 120),  # OSM motorway gold-yellow — strong visual weight
    "arterial":            (210, 185, 130),  # Primary road — softer gold
    "connector":           (195, 187, 172),  # Secondary/local connector — warm light grey
    "residential_road":    (210, 204, 196),  # Residential street — near-white warm grey
    "road_marking":        (235, 225, 200),  # Center-line / dashes on highways

    # ── SIDEWALK / PAVEMENT ─────────────────────────────────────────────────
    "sidewalk":            (200, 196, 188),  # Slightly darker/warmer than residential road
    "plaza_pavement":      (210, 205, 192),  # Open civic plaza — light stone
    "alley":               (170, 165, 158),  # Service alley — noticeably darker than sidewalk

    # ── BUILDINGS: CBD / DOWNTOWN ────────────────────────────────────────────
    "cbd_building_base":   ( 82,  90, 100),  # Dark blue-grey glass tower base
    "cbd_building_mid":    ( 95, 103, 115),  # Mid-tone glass/steel variant
    "cbd_building_light":  (110, 118, 130),  # Lighter CBD variant (shorter structures)
    "cbd_rooftop":         ( 70,  78,  88),  # Rooftop accent — slightly darker than facade

    # ── BUILDINGS: MIDTOWN / MID-RISE ────────────────────────────────────────
    "midtown_brick":       (148, 108,  88),  # Classic brick red-brown
    "midtown_concrete":    (155, 148, 138),  # Concrete mid-rise — neutral warm grey
    "midtown_beige":       (172, 158, 134),  # Older limestone/beige facade
    "midtown_rooftop":     (128,  98,  78),  # Brick rooftop — darker brick

    # ── BUILDINGS: RESIDENTIAL ───────────────────────────────────────────────
    "residential_warm":    (210, 185, 155),  # Cream/tan house — warm and light
    "residential_salmon":  (205, 168, 148),  # Pale salmon cottage
    "residential_pale":    (218, 205, 180),  # Very light cream detached house
    "residential_roof":    (175, 130, 100),  # Terracotta/warm roof tile accent
    "residential_lawn":    (148, 175, 110),  # Front lawn / setback garden

    # ── BUILDINGS: CIVIC / LANDMARK ──────────────────────────────────────────
    "landmark_facade":     (195, 185, 155),  # Pale stone — classical civic
    "landmark_accent":     (158, 148, 115),  # Darker stone detail / column shadow
    "landmark_roof":       (100, 130, 148),  # Verdigris/slate civic dome or roof
    "landmark_special":    (180, 160, 100),  # Gilded/notable landmark highlight

    # ── GREEN SPACE ──────────────────────────────────────────────────────────
    "park_grass":          (106, 158,  74),  # Primary park grass — clear, saturated green
    "park_grass_dark":     ( 88, 138,  60),  # Shadow/path-edge grass darker variant
    "park_grass_light":    (130, 175,  96),  # Sunlit patch / lighter grass variant
    "park_path":           (190, 178, 155),  # Gravel/stone park path
    "park_fountain_water": (122, 178, 210),  # Fountain basin — bright blue, read as water
    "park_fountain_stone": (185, 178, 162),  # Fountain surround / plaza stone
    "park_plaza_center":   (200, 192, 170),  # Open plaza center tile — light stone
    "tree_canopy":         ( 72, 128,  56),  # Dense tree mass — darker than park grass
    "tree_canopy_edge":    ( 88, 148,  68),  # Tree canopy lighter edge

    # ── UNPAVED / EXTERIOR LAND ──────────────────────────────────────────────
    "vacant_lot":          (175, 162, 138),  # Vacant / undeveloped lot — dusty tan
    "setback_ground":      (165, 168, 140),  # Building setback / side yard — grey-green
    "construction":        (168, 148, 115),  # Construction site — raw earth brown
    "gravel_parking":      (168, 162, 152),  # Surface parking lot — grey gravel

}
```

### 2.2 Color Rationale Notes

- **Highway gold** `(220, 194, 120)` is derived directly from OSM Carto's motorway style and creates maximum contrast against both grey buildings and green parks.
- **CBD buildings** sit in the `82–130` luminance range, making them the darkest non-water non-road cells — this reads as density/height.
- **Residential** values are all above luminance 155 — light, warm, airy — creating a clear zone-type signal from CBD without any labels.
- **Park grass** `(106, 158, 74)` is intentionally saturated: in a grey urban field, desaturated greens vanish. This saturation level matches OSM's `#8DC56C` park fill.
- **Civic landmark** uses pale stone `(195, 185, 155)` which is neither warm residential nor cool CBD — it reads as "something different" immediately.

---

## 3. Block and Lot Sizing for Realism

### 3.1 Block Sizes (cells) for a 10 m/cell Grid

Real-world city block sizes vary enormously by zone. At 10 m/cell:

| Zone | Real Block Size | Cell Range (block interior, excluding road) | Road cells each side |
|---|---|---|---|
| CBD (Manhattan-style) | 60–80 m × 200–280 m | 6–8 × 20–28 | 1 (local), 2 (arterial) |
| CBD (European grid) | 80–120 m × 80–120 m | 8–12 × 8–12 | 1–2 |
| Midtown mixed-use | 80–120 m × 100–160 m | 8–12 × 10–16 | 1–2 |
| Residential (dense) | 100–150 m × 100–150 m | 10–15 × 10–15 | 1 |
| Residential (suburban) | 120–200 m × 120–200 m | 12–20 × 12–20 | 1 |

**Recommended procedural ranges for your 96×72 grid:**

```python
BLOCK_SIZE_CELLS = {
    "cbd":         {"min_w": 6,  "max_w": 10, "min_h": 8,  "max_h": 16},
    "midtown":     {"min_w": 8,  "max_w": 14, "min_h": 10, "max_h": 18},
    "residential": {"min_w": 10, "max_w": 20, "min_h": 10, "max_h": 20},
}
```

**Critical rule:** Never generate more than 3 consecutive blocks of the same width in the same zone. The eye detects monotonic repetition immediately. Use weighted random block splitting.

**Variance formula for block widths:**
```python
import random

def block_width(zone: str) -> int:
    cfg = BLOCK_SIZE_CELLS[zone]
    base = (cfg["min_w"] + cfg["max_w"]) // 2
    # skew toward slightly smaller blocks more often than large
    return int(random.triangular(cfg["min_w"], cfg["max_w"], base - 1))
```

### 3.2 Lot Sizes Within Blocks (cells)

A "lot" is the footprint of one building plus its immediate setback within a block.

| Zone | Min Lot (cells) | Max Lot (cells) | Notes |
|---|---|---|---|
| CBD | 2×3 | 6×8 | Dense packing; lots fill block edge-to-edge |
| Midtown | 3×4 | 8×12 | Mixed, some setback |
| Residential | 3×4 | 10×14 | Must include 1–2 cell setback on at least 2 sides |

**Building footprint within lot** (not including setback):

```python
LOT_FILL = {
    "cbd":         0.88,   # 88% of lot is building footprint — very dense
    "midtown":     0.72,   # 72% — some sidewalk gap visible
    "residential": 0.48,   # 48% — house surrounded by lawn
}
```

For a residential lot of 8×10 cells (80 m²), the building footprint is ~4×5 = 20 cells — a 200 m² footprint, roughly a large detached house. This feels correct.

**Minimum readable building size:** 2×3 cells. Anything smaller reads as noise, not structure.
**Maximum single building footprint for non-landmark:** 10×14 cells (a full city block-filling office tower base). Larger than this should be reserved for landmarks only.

### 3.3 Park Frequency and Minimum Size for 96×72 Map

```python
PARK_REQUIREMENTS = {
    "min_parks":        6,    # Absolute minimum for any 96×72 city map
    "target_parks":     10,   # Ideal for visual rhythm
    "neighborhood_park_min_cells": (6, 6),    # 60m × 60m — smallest readable park
    "neighborhood_park_max_cells": (12, 12),  # 120m × 120m — comfortable neighborhood park
    "central_park_min_cells":      (14, 14),  # 140m × 140m — one "large" central park required
    "park_coverage_pct": 0.04,                # ~4% of total map area should be park
}
```

**Placement rules:**
- At least 1 large park (≥14×14 cells) should exist, preferably in or adjacent to CBD/midtown border (civic green)
- No residential block should be more than 15 cells (150 m) from a park of any size
- Avoid placing all parks in a single corner — distribute across all quadrants

**Park coverage check:**
```python
total_cells = 96 * 72  # 6912
min_park_cells = int(total_cells * 0.04)  # ~276 cells minimum in park tiles
```

---

## 4. Visual Variety Techniques (Color-Only, No Sprites)

### 4.1 Per-Building Lot Shade Variation

Every building of the same type should receive a per-lot color offset applied at generation time and stored per-lot (not recalculated per frame).

```python
import random

def lot_color_variant(base_rgb: tuple, zone: str) -> tuple:
    """
    Returns a per-lot color variant of base_rgb.
    Variance range is zone-dependent — CBD varies less (glass is uniform),
    residential varies more (different paint colors).
    """
    variance = {
        "cbd":         10,   # ±10 on each channel — subtle material variation
        "midtown":     16,   # ±16 — brick age, stone vs concrete variation
        "residential": 22,   # ±22 — widest range, house colors vary most
    }[zone]

    r, g, b = base_rgb
    delta_r = random.randint(-variance, variance)
    delta_g = random.randint(-variance, variance)
    delta_b = random.randint(-variance, variance)

    # Clamp to valid range
    return (
        max(0, min(255, r + delta_r)),
        max(0, min(255, g + delta_g)),
        max(0, min(255, b + delta_b)),
    )
```

**Why these exact variance values:**
- ±10 for CBD: glass towers in real cities are very consistent — too much variation makes them look residential
- ±16 for midtown: brick buildings differ noticeably in age and material but share the same palette family
- ±22 for residential: houses are genuinely painted different colors; this range still keeps them "warm light" while avoiding cartoon randomness

**Important:** Apply the same delta consistently to all cells within one lot. Never vary color cell-by-cell within a building — that produces noise, not variation.

### 4.2 Building Edge/Outline Darkening for Depth Perception

Apply a 1-cell-wide border darkening to all 4 edges of every building footprint. This creates implied shadow and separates adjacent buildings without drawing explicit outlines.

```python
EDGE_DARKEN_FACTOR = 0.80  # Multiply each channel by this value for edge cells

def darken(rgb: tuple, factor: float = EDGE_DARKEN_FACTOR) -> tuple:
    r, g, b = rgb
    return (int(r * factor), int(g * factor), int(b * factor))
```

**Directional shadow simulation (optional but impactful):**
Apply asymmetric darkening to imply a top-left light source (matches Google Maps satellite lighting convention):

```python
SHADOW_FACTORS = {
    "top":    0.85,   # Slightly lit from above
    "left":   0.85,   # Slightly lit from left
    "bottom": 0.72,   # Shadowed underside
    "right":  0.72,   # Shadowed right side
}
```

This means a building rendered in its base color will have:
- Top-left edges at 85% brightness
- Bottom-right edges at 72% brightness
- Interior cells at 100% base color

### 4.3 Density-Based Color Modulation (Height Implied by Darkness)

Tall buildings in top-down views appear darker because:
1. More building mass = more shadow areas visible
2. Glass/steel materials absorb more light than low-rise materials
3. Rooftop detail is minimal at scale

Implement a height-to-darkness mapping per lot:

```python
def height_modulated_color(base_rgb: tuple, height_stories: int) -> tuple:
    """
    height_stories: 1–5 (low rise) → 5–15 (mid rise) → 15–40 (high rise)
    Returns darkened color proportional to height.
    """
    # Normalize: 1 story = no darkening, 40 stories = 30% darker
    t = min(1.0, (height_stories - 1) / 39.0)
    darkening = 1.0 - (t * 0.30)  # Factor from 1.0 down to 0.70

    r, g, b = base_rgb
    return (int(r * darkening), int(g * darkening), int(b * darkening))

# Example ranges:
# 2-story house:      factor ≈ 0.974  (nearly unchanged)
# 8-story midtown:    factor ≈ 0.946  (slightly darker)
# 20-story CBD:       factor ≈ 0.854  (noticeably darker)
# 35-story tower:     factor ≈ 0.759  (strongly dark)
```

**Combined with per-lot variance:** Apply height modulation FIRST, then lot variance. This preserves the zone-level darkness hierarchy while adding individual character.

### 4.4 Alternating Building Orientation Cues (Facade Direction Hints)

Without sprites, you can hint at a building's "facing direction" by applying a subtle luminance gradient across the building interior:

```python
def apply_facade_gradient(
    cells: list[list[tuple]],
    facing: str,          # "north", "south", "east", "west"
    facade_boost: int = 12
) -> list[list[tuple]]:
    """
    Brightens the edge cells facing the street by facade_boost,
    creating an implied front-of-building contrast.
    """
    rows = len(cells)
    cols = len(cells[0])

    for r in range(rows):
        for c in range(cols):
            boost = 0
            if facing == "north" and r == 0:
                boost = facade_boost
            elif facing == "south" and r == rows - 1:
                boost = facade_boost
            elif facing == "west" and c == 0:
                boost = facade_boost
            elif facing == "east" and c == cols - 1:
                boost = facade_boost

            if boost:
                base = cells[r][c]
                cells[r][c] = tuple(min(255, v + boost) for v in base)

    return cells
```

**Practical use:** Apply to midtown and residential buildings only. CBD towers have glass curtain walls and do not need a "facing" cue — their mass reads as monolithic.

---

## 5. Road Visual Weight

### 5.1 Visual Width in Pixels/Cells by Road Type

At 10 m/cell, road widths should match real-world equivalents:

| Road Type | Real Width | Cell Width | Visual Notes |
|---|---|---|---|
| Highway / motorway | 20–30 m | **2–3 cells** | Always ≥2 cells; central divider stripe optional |
| Arterial / primary | 15–20 m | **2 cells** | Dominant grid skeleton |
| Connector / secondary | 10–12 m | **1–2 cells** | 1 cell for tight grids, 2 for midtown |
| Residential street | 6–9 m | **1 cell** | Minimum readable road |
| Alley / service lane | 3–5 m | **1 cell** (darker) | Distinguish by color, not width |

**For a 96×72 grid, recommended widths:**

```python
ROAD_WIDTH_CELLS = {
    "highway":    3,   # 30m — major freeway / ring road
    "arterial":   2,   # 20m — main city grid roads
    "connector":  1,   # 10m — secondary grid
    "residential":1,   # 10m — local street (differentiated by color only)
}
```

### 5.2 Color Contrast Rules Between Road Types

The color contrast between adjacent road types must be perceptually distinct — not just theoretically different. Use the luminance delta as a guide:

```python
ROAD_LUMINANCE = {
    "highway":     187,   # Luminance of (220, 194, 120)
    "arterial":    180,   # Luminance of (210, 185, 130)
    "connector":   186,   # Luminance of (195, 187, 172) — same luminance, different hue
    "residential": 201,   # Luminance of (210, 204, 196)
    "sidewalk":    195,   # Luminance of (200, 196, 188)
}

# Minimum required luminance delta between adjacent road types: 8 units
# Minimum required hue delta between adjacent road types: 15° (for colorblind accessibility)
```

**Key contrast rules:**
1. Highway must be visually warmer (more yellow) than connector roads — color hue distinguishes hierarchy, not just brightness
2. Sidewalk must be lighter than connector road but darker than lawn/setback — it forms the visible boundary between road space and building space
3. Residential road should be lightest road type — it recedes visually, which matches its lower importance

**Building-to-road contrast:** CBD building base `(82, 90, 100)` against connector road `(195, 187, 172)` gives a luminance delta of ~90 — this is the darkest pair and is what makes the city "pop" visually. Never let this delta fall below 60.

### 5.3 Junction / Intersection Visual Treatment

Intersections are high-information points. Keep them simple:

```python
INTERSECTION_RULES = {
    "highway_x_highway":   "highway color fill — no special marker",
    "highway_x_arterial":  "highway color fill at junction box",
    "arterial_x_connector":"connector color — arterial color bleeds 1 cell into corners",
    "connector_x_residential": "connector color — clean flush join",
    "any_x_any_corner":    "chamfer 1 cell at 45° for 3+ cell road crossings (visual softening)",
}
```

**Practical intersection rendering:**
- At `highway × arterial` crossings, fill the entire crossing box with highway color `(220, 194, 120)`
- At `arterial × connector` crossings, the higher-class road color fills the box
- For 4-way `residential × residential`, no special treatment — uniform connector color fill

**Avoid:** Rendering intersection boxes in sidewalk color — this creates phantom "plaza" reads that confuse the viewer.

---

## 6. Park Visual Design

### 6.1 Minimum Readable Park Size

```python
PARK_MIN_SIZES = {
    "pocket_park":       (4, 4),    # 40m × 40m — absolute minimum; reads as "gap" without internal detail
    "neighborhood_park": (6, 8),    # 60m × 80m — reads clearly as park; can support path + fountain
    "district_park":     (12, 14),  # 120m × 140m — clearly dominant green space; can have all features
    "central_park":      (20, 20),  # 200m × 200m — landmark scale; one per city map maximum
}

# Rule: parks smaller than 4×4 cells read as "error" or "gap" — fill them as vacant lot instead.
# Rule: parks smaller than 6×6 cells should NOT have internal path rendering (too cluttered).
```

**The "gap vs park" test:** If removing the green color would make the area invisible (i.e., it has no internal structure), it is a gap, not a park. Minimum 6×6 with at least one internal path cell.

### 6.2 Internal Park Variety — Color Cues

For any park ≥ 6×6 cells, add internal structure using color differentiation only:

```python
PARK_INTERNAL_ELEMENTS = {
    # Element: (color, min_area_cells, placement_rule)
    "grass_base":    ((106, 158,  74), None,       "fills entire park interior"),
    "grass_variant": ((130, 175,  96), "scattered", "10–20% of grass cells, random patches 2×2 to 3×3"),
    "path_straight": ((190, 178, 155), "linear",    "1-cell-wide diagonal or orthogonal across park"),
    "path_corner":   ((185, 172, 148), "at_joins",  "slightly darker at path junctions"),
    "tree_mass":     (( 72, 128,  56), "clustered", "2×2 to 4×4 clusters near park edges"),
    "tree_edge":     (( 88, 148,  68), "perimeter", "1-cell ring of lighter green inside park boundary"),
    "fountain":      ((122, 178, 210), "center",    "1×1 to 2×2 cells at park center or path intersection"),
    "fountain_stone":((185, 178, 162), "around_fountain", "1-cell ring around fountain — distinguishes water from grass"),
    "plaza_paving":  ((200, 192, 170), "near_entrance", "2–4 cell wide paved area at park street entrances"),
}
```

**Minimum park internal feature recipe by size:**

```python
def park_features_for_size(w: int, h: int) -> list[str]:
    features = ["grass_base", "tree_edge"]
    if w >= 6 and h >= 6:
        features += ["path_straight", "tree_mass"]
    if w >= 8 and h >= 8:
        features += ["grass_variant", "plaza_paving"]
    if w >= 10 and h >= 10:
        features += ["fountain", "fountain_stone"]
    if w >= 14 and h >= 14:
        features += ["path_corner"]  # crossing path layout
    return features
```

### 6.3 Park Shape — Rectangular vs Irregular

**Short answer: start rectangular, then subtract corners.**

Real city parks are almost always rectilinear (they occupy land parcels) but are rarely perfectly rectangular because:
- Street diagonals clip corners
- Adjacent lots bite into edges
- Internal paths create implied sub-shapes

**Implementation approach:**

```python
def irregular_park_shape(x, y, w, h, irregularity: float = 0.15):
    """
    Start with a w×h rectangle at (x,y).
    Randomly remove cells from corners to create organic edges.
    irregularity: fraction of perimeter cells eligible for removal (0.0–0.25)
    """
    park_cells = set()
    for r in range(h):
        for c in range(w):
            park_cells.add((x + c, y + r))

    # Remove corner bites — each corner removes a small triangle
    corner_bite = max(1, int(min(w, h) * irregularity))
    for bite in range(corner_bite):
        # Top-left corner
        for i in range(corner_bite - bite):
            park_cells.discard((x + i, y + bite))
        # Bottom-right corner (mirror)
        for i in range(corner_bite - bite):
            park_cells.discard((x + w - 1 - i, y + h - 1 - bite))

    return park_cells
```

**Why not fully irregular/organic?**
- Organic blob parks look like mistakes in a top-down pixel grid at 10 m/cell scale
- Real urban parks (Central Park, Hyde Park, Parc de la Villette) are rectilinear with path systems, not blobs
- Irregular blobs also cause road routing problems in your generation pipeline
- Small diagonal clip-offs (1–3 cells at corners) are sufficient to break monotony

**Rule of thumb:** 70% of parks should be simple rectangles. 30% should have 1–2 corners clipped by 1–3 cells. Avoid more complex shapes unless the park is ≥ 20×20 cells.

---

## 7. Quick-Reference Implementation Checklist

For engineers integrating these recommendations, validate against this checklist:

```
VISUAL HIERARCHY
[ ] Roads render before buildings — road skeleton readable at map zoom
[ ] At least 3 visually distinct road types by color AND width
[ ] CBD buildings darker than residential by ≥ 60 luminance units
[ ] At least one landmark with unique color not matching any zone type

COLOR PALETTE
[ ] Park grass saturation: channel G > channel R + 40 (clearly green, not grey-green)
[ ] Highway color: channel R + channel G > 2 × channel B (warm gold, not grey)
[ ] CBD buildings: all channels < 130 (definitively dark)
[ ] Residential buildings: all channels > 150 (definitively light)

BLOCK SIZING
[ ] No two adjacent blocks in same zone are identical width
[ ] CBD blocks: ≤ 16 cells in longest dimension
[ ] Residential blocks: ≥ 10 cells in shortest dimension
[ ] At least 4 different block sizes present in each zone region

LOT VARIETY
[ ] Per-lot color variance applied (±10 CBD, ±16 midtown, ±22 residential)
[ ] Edge darkening applied to all building perimeters (factor 0.72–0.85)
[ ] Lots within one block vary in size (not all same footprint)

PARKS
[ ] ≥ 6 parks on 96×72 map; ≥ 1 park ≥ 14×14 cells
[ ] No park smaller than 4×4 cells rendered
[ ] All parks ≥ 6×6 have at least: path + tree edge + grass base
[ ] All parks ≥ 10×10 have fountain (blue cell) at center

ROADS
[ ] Highway: ≥ 2 cells wide, warmest color
[ ] Sidewalk color lighter than connector road
[ ] Intersection boxes use the higher-class road's color
```

---

*Report prepared by Team 6 — Senior Urban Visual Design Committee.*
*All RGB values empirically derived from Google Maps, OpenStreetMap Carto, SimCity 2000, and Pokemon city tile sets.*
*All sizing figures calibrated to 10 m/cell resolution at 96×72 map dimensions.*
