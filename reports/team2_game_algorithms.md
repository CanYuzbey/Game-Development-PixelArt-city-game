# Procedural City Map Generator — Algorithm Research Report
**Team 2 | Senior Game Developer Research**
**Date:** 2026-05-09
**For:** Implementation Team — Python Tile-Grid City Generator

---

## Executive Summary

This report surveys the academic and open-source landscape of procedural city generation and translates findings into concrete, Python-ready algorithms for the existing tile-grid system (10 m/cell, 64×48–96×72, cardinal-direction bitmask connectivity). All pseudo-code targets the actual system constraints: no diagonal tiles, 16 bitmask shapes, seed-based deterministic RNG, zone layers (CBD / Midtown / Residential).

---

## 1. Foundational Academic Papers

### 1.1 Parish & Müller 2001 — "Procedural Modeling of Cities" (SIGGRAPH 2001)

**What it does:** Given input raster maps (land/water mask, population density), it generates a complete city: road hierarchy, block subdivision, and 3-D building geometry.

**Key algorithm bullets:**
- Uses an extended L-system with two rule sets: *global goals* (steer roads toward high-density areas using population map sampling) and *local constraints* (snap to nearby intersections, avoid water, stop at map edges).
- Road segments are placed one at a time via a priority queue sorted by `time_delay`. Each dequeued segment checks local constraints before committing; if compatible, it seeds new branch segments back into the queue.
- Two road tiers: *highways* (long, low-curvature, high priority) and *streets* (shorter, denser, branch off highways). Highways are grown first; streets fill the resulting blocks.
- Block interiors are subdivided into lots using recursive OBB (Oriented Bounding Box) splitting — find the longest axis of the block polygon, cut perpendicular to it, recurse until lots reach a minimum-area threshold.
- Lot geometry is handed to a separate CGA Shape Grammar engine that generates 3-D building facades; this part is irrelevant to 2-D tile systems.

**Relevance to our system:** The priority-queue road grower directly matches our existing highway "spine walker." The OBB lot subdivision is the clearest path to parcel generation. The two-tier road hierarchy (highway + street) maps onto our highway + connector phases.

---

### 1.2 Chen et al. 2008 — "Interactive Procedural Street Modeling" (SIGGRAPH 2008)

**What it does:** Instead of L-systems, it guides road layout via a continuous *tensor field* that encodes preferred street directions at every point in the plane. Users paint tensor field strokes; the system integrates streamlines through the field to produce the road graph.

**Key algorithm bullets:**
- A tensor field T(x,y) stores a 2×2 symmetric matrix per point encoding two orthogonal eigenvector directions (principal street directions).
- *Streamline integration:* starting from seed points, follow the major eigenvector of T using a simple RK4 ODE integrator, placing road vertices at fixed arc-length steps until hitting water, another road, or the map boundary.
- Separating distance `d_sep` prevents streamlines from running too close together — if a candidate step lands within `d_sep` of an existing road, integration stops.
- The tensor field can be composed from multiple basis fields: grid fields (constant direction), radial fields (roads radiating from a point — good for city centers), and noise fields (organic variation).
- Post-process: snap near-intersections, merge short road stubs, compute the planar graph.

**Key difference from Parish:** Parish grows roads greedily one segment at a time (local). Chen integrates continuous curves through a global field first, then discretizes. Chen gives the user far more shape control but is harder to implement.

**Relevance:** The *radial field* concept around the CBD is immediately useful: roads near the city center can be biased to converge toward the center point, creating the spoke-and-ring pattern of real CBDs, without requiring a full tensor field implementation. A simplified version: for cells within the CBD zone, rotate the preferred road direction by a small angle toward the CBD centroid.

---

### 1.3 Vanegas et al. 2012 — "Procedural Generation of Parcels in Urban Modeling" (EG 2012)

**What it does:** A dedicated parcel (lot) subdivision system that takes block polygons and a set of user-controllable style parameters and outputs realistic, street-accessible lots.

**Key algorithm bullets:**
- Combines two subdivision strategies: *OBB splitting* (good for grid-plan blocks — Manhattan, Barcelona) and *straight skeleton subdivision* (good for irregular blocks — medieval cities, organic layouts).
- For OBB splitting: compute the oriented bounding box of the block; split along the shorter axis at a position sampled from a configurable distribution (center ± noise); recurse until area < `min_lot_area` or width < `min_lot_width`.
- For straight skeleton: erode the block polygon inward uniformly (the skeleton is the locus of centers of the largest inscribed circles). Skeleton edges become back-lot boundaries; lots extend from the street frontage to the skeleton.
- Introduces a *frontage constraint*: every lot must have a minimum street-facing width (typically 6–20 m in real cities). Lots that fail this constraint are merged with a neighbor.
- Performance: can generate 500,000 parcels in under 3 seconds on contemporary hardware.

**Relevance:** For a cardinal-direction tile grid, OBB splitting degenerates to simple axis-aligned rectangle splitting — the easiest possible case. The frontage constraint translates to: "every lot must touch at least one road-adjacent edge of the block."

---

## 2. Open-Source Implementations to Study

### 2.1 `josauder/procedural_city_generation`
- **Language/Framework:** Python 3, visualized in Blender
- **Algorithm:** Road graph built from a Voronoi-based vertex network; cycles (city blocks) extracted by finding all vertex triples connected in the graph sorted by angle to the x-axis. Buildings are placed by subdividing block polygons vertically.
- **Reusable for our system:** The cycle-detection algorithm (block extraction from a planar road graph) is directly applicable. Their approach of sorting edges by angle around each vertex to find the minimal enclosing face is the canonical planar graph face enumeration algorithm.
- **Repo:** https://github.com/josauder/procedural_city_generation

### 2.2 `t-mw/citygen` (JavaScript, also `t-mw/citygen-godot` GDScript port)
- **Language/Framework:** JavaScript (browser demo); GDScript (Godot 3 port)
- **Algorithm:** Faithful re-implementation of Parish & Müller 2001. Priority-queue road grower with population-density noise map (three octaves of simplex noise combined). Local constraints: crossing generation, junction snapping, dead-end extension. A* pathfinding for highway routing between high-density seed points.
- **Reusable:** The local constraint logic (snap within `d_snap` radius to existing junction, extend to nearby road endpoint) is directly portable to Python and maps well onto tile coordinates. The simplex noise population map is a drop-in replacement for our existing FBM Perlin noise.
- **Repo:** https://github.com/t-mw/citygen | https://github.com/t-mw/citygen-godot

### 2.3 `mxgmn/WaveFunctionCollapse`
- **Language/Framework:** C# (reference implementation); dozens of Python ports exist
- **Algorithm:** Constraint propagation over a tile grid. Each cell starts with a superposition of all possible tiles; collapsing one cell propagates adjacency constraints to neighbors via arc consistency, reducing their possibility sets. Repeat until all cells collapsed or contradiction reached.
- **Reusable:** The adjacency rule extraction step is directly applicable as a post-pass on top of our bitmask system (see Section 5).
- **Repo:** https://github.com/mxgmn/WaveFunctionCollapse

---

## 3. Lot / Parcel Subdivision Algorithms

### 3.1 The Three Main Methods

**OBB (Oriented Bounding Box) Splitting**
Compute the axis-aligned bounding rectangle of a block. Split it along the shorter axis at a position near the midpoint (with optional noise offset). Recurse on each half. Stop when area < `min_area` or width < `min_width`. For our cardinal-direction grid, OBB always aligns with the tile grid — no rotation needed. This is the simplest correct implementation.

**Straight Skeleton Subdivision**
Erode the block polygon inward at equal speed from all edges simultaneously. The skeleton (medial axis) partitions the block such that each lot has a well-defined frontage on one street edge. Harder to implement on a tile grid because it requires polygon offset operations.

**Recursive Axis-Alternating Splitting (Recommended for tile grids)**
A simplified version of OBB splitting that alternates the split axis each recursion level (similar to a k-d tree). Produces naturally rectangular lots aligned to the cardinal grid. See pseudo-code in Section 7.

### 3.2 Minimum Width Constraint
Real lots require at least 6 m frontage (one tile at our scale, since 1 cell = 10 m). The practical minimum for a buildable lot in our system: width ≥ 2 cells (20 m), depth ≥ 2 cells. Lots smaller than 2×2 become parks or empty lots.

### 3.3 Recommendation for Our System
Use **recursive axis-alternating splitting** (Section 7.2). It is:
- Trivially aligned to our cardinal tile grid
- O(n log n) in the number of lots produced
- Deterministic given the same seed
- Easy to bias: split the longer axis preferentially to get more elongated lots in Residential zones, more square lots in CBD

---

## 4. Landmark and Special Zone Placement

### 4.1 Anchor-Point Approach (Used in Cities: Skylines)
Place one "seed" landmark first (town hall, cathedral, market square) at a high-value location — typically the Chebyshev centroid of the CBD zone. Then let the surrounding road network respond: connectors within a configurable radius `r_civic` are upgraded (wider, higher connectivity), and adjacent blocks are marked as mixed-use rather than pure residential.

**Implementation:** After zone assignment, pick the cell with the minimum Chebyshev distance to the CBD center. Mark it as `CIVIC_ANCHOR`. During connector generation, cells within 3 tiles of `CIVIC_ANCHOR` receive a connector probability boost of +0.3 (more dense street grid around the civic center).

### 4.2 Park Placement
Two strategies used in real city generators:
1. **Large block threshold:** After block detection, any block with area > `park_max_area` (e.g., 12×12 = 144 cells) OR area < `park_min_area` (e.g., 2×2 = 4 cells) is converted to a park. Large blocks = couldn't be usefully subdivided; tiny blocks = not buildable.
2. **Zone-weighted random:** In Residential zones far from highways (distance > 8 cells), convert 8–12% of detected blocks to parks using seeded RNG.

### 4.3 Civic Building Patterns
Observed in Parish & Müller and Cities: Skylines:
- **Town Hall / Civic Center:** Always at the geometric center of the CBD, on a corner lot facing two streets. Reserve a 3×3 cell footprint.
- **Market Square:** An open block (no building, park tile) at the intersection of two highways or major connectors, usually at the CBD/Midtown boundary.
- **Religious Buildings:** Placed at high-ground cells (elevated noise value from the coastline FBM) within Midtown, facing a main connector. Footprint: 2×3 cells.
- **Industrial / Port:** Along the coastline (land cells adjacent to water cells), in the lowest-zone areas.

---

## 5. WFC (Wave Function Collapse) for City Tiles

### 5.1 How WFC Applies to Road Tile Selection
In a pure WFC road system, each cell starts as a superposition of all 16 bitmask tile types. Adjacency rules encode which tile can be placed next to which: e.g., a tile with an East exit (bit 4 set) must be adjacent to a tile with a West exit (bit 1 set). WFC collapses cells one at a time, propagating constraints.

### 5.2 Pros vs. Our Bitmask System

| Aspect | Our Bitmask System | WFC |
|---|---|---|
| Speed | O(n) — one pass per cell | O(n log n) — constraint propagation |
| Determinism | Fully deterministic | Deterministic given seed and collapse order |
| Global coherence | Good (phases enforce structure) | Excellent (global constraint satisfaction) |
| Contradiction risk | None | Present — must handle backtracking |
| Artistic control | Medium (phase parameters) | High (tile weights, forbidden patterns) |
| Implementation complexity | Low | Medium-High |

### 5.3 Hybrid Approach (Recommended)
Use our existing bitmask system as the **primary road layout engine** (Phases 1–5 as-is). Then apply a **WFC post-pass** only for aesthetic tile selection within each bitmask category. For example, a straight N-S road tile (bitmask 0b1010 = 10) might have three visual variants: plain, with manhole cover, with center stripe. WFC selects among these variants using local frequency constraints (no two manholes adjacent, stripes must continue for at least 3 tiles).

This gives the coherence benefits of WFC without risking road-graph contradictions. The bitmask guarantees connectivity; WFC only affects visuals.

**Implementation cost:** ~150–200 LOC. Define a `VisualVariantWFC` class that operates on a second tile layer (visual layer) after the road layer is fully committed.

---

## 6. Variation and Imperfection Techniques

### 6.1 Breaking Grid Monotony

**Irregular block sizes:** When generating connector grid lines, instead of spacing them at a fixed interval `s`, sample the interval from `s + noise(x,y) * s * 0.3`. This creates blocks of varying sizes while maintaining rough grid alignment. Our existing zone-aware density dropout already partially achieves this.

**Offset grid lines:** Alternate connector rows between two slightly different x-offsets. Row at y: connectors at x = {0, s, 2s, ...}. Row at y+s: connectors at x = {s/3, s+s/3, ...}. Produces a staggered block pattern resembling real residential grids.

**Noise-perturbed intersections:** After placing connectors, for each intersection cell that is not a highway cell, apply a small random displacement: with probability 0.1, shift the intersection 1 cell in a random cardinal direction and re-run the bitmask calculation for the affected cells. Creates T-junctions and slight misalignments that feel organic.

### 6.2 Residential vs. CBD Differentiation Without New Tile Types

Since we are limited to existing tile types, differentiation is achieved through **density and pattern**, not new geometry:
- **CBD:** High connector density (grid spacing 2–3 cells), near-zero dropout probability, roundabouts at major intersections, both highway arteries.
- **Midtown:** Medium density (grid spacing 4–5 cells), 10–15% dropout, occasional diagonal connector.
- **Residential:** Low density (grid spacing 6–8 cells), 25–40% dropout, cul-de-sacs (dead-end stubs), no roundabouts.
- **Dead-end stubs:** In Residential zones, when a connector would be dropped, instead extend it 1–2 cells and terminate. This creates the "dead-end street" pattern characteristic of suburban residential areas.

### 6.3 Stochastic Street Dropping
Our existing zone-aware density dropout is consistent with techniques used in:
- **tmwhere citygen:** Population density map directly controls local road density — high density = more roads, low density = sparse roads.
- **Parish & Müller:** The L-system branching probability is modulated by the population map value at each candidate branch point.
- **Mini Metro (inferred from gameplay):** Procedural route generation uses demand density to place stations; low-demand areas have sparse coverage.

The key refinement: instead of a flat per-zone dropout probability, use `dropout = base_rate * (1 - population_noise(x, y) * 0.5)` where `population_noise` is an independent noise octave. This makes dropout spatially correlated (whole neighborhoods get fewer streets) rather than uniformly random (every other cell drops).

---

## 7. Specific Ready-to-Implement Algorithms

### 7.1 Block Detection (BFS Flood Fill)

Finds all enclosed areas bounded by road cells. Run after all road phases are complete.

```python
from collections import deque

ROAD_TILES = {HIGHWAY, CONNECTOR, SIDEWALK}  # any road cell type

def detect_blocks(grid, width, height):
    """
    Returns list of blocks. Each block is a set of (row, col) tuples
    representing non-road cells enclosed by roads or the map boundary.
    Cells touching the map edge are excluded (they form the 'outside' region).
    """
    visited = [[False] * width for _ in range(height)]
    blocks = []

    for start_r in range(height):
        for start_c in range(width):
            cell = grid[start_r][start_c]
            if visited[start_r][start_c] or cell.tile_type in ROAD_TILES:
                visited[start_r][start_c] = True
                continue

            # BFS from this unvisited non-road cell
            region = []
            queue = deque([(start_r, start_c)])
            visited[start_r][start_c] = True
            touches_edge = False

            while queue:
                r, c = queue.popleft()
                region.append((r, c))
                if r == 0 or r == height-1 or c == 0 or c == width-1:
                    touches_edge = True

                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < height and 0 <= nc < width:
                        if not visited[nr][nc] and grid[nr][nc].tile_type not in ROAD_TILES:
                            visited[nr][nc] = True
                            queue.append((nr, nc))

            # Exclude the exterior region (touches map edge)
            if not touches_edge:
                blocks.append(set(region))

    return blocks
```

**Complexity:** O(W×H) — each cell is visited exactly once.

---

### 7.2 Lot Subdivision (Alternating Axis Splitting)

Splits a rectangular block into building lots using recursive axis-alternating binary splitting.

```python
def subdivide_block_into_lots(block_cells, rng, min_lot_width=2, min_lot_height=2):
    """
    block_cells: set of (row, col) tuples forming a rectangular block
    rng: seeded random.Random instance
    Returns: list of lots, each a set of (row, col) tuples
    """
    if not block_cells:
        return []

    rows = [r for r, c in block_cells]
    cols = [c for r, c in block_cells]
    r_min, r_max = min(rows), max(rows)
    c_min, c_max = min(cols), max(cols)
    height = r_max - r_min + 1
    width  = c_max - c_min + 1

    # Base case: block is too small to split further
    if height < min_lot_height * 2 and width < min_lot_width * 2:
        return [block_cells]

    # Choose split axis: prefer the longer dimension
    split_horizontal = (height >= width)

    if split_horizontal and height >= min_lot_height * 2:
        # Split along a row line
        # Choose split point with noise: center ± 20%
        mid = (r_min + r_max) // 2
        offset = int(rng.uniform(-height * 0.2, height * 0.2))
        split_row = mid + offset
        split_row = max(r_min + min_lot_height, min(r_max - min_lot_height, split_row))

        top_cells    = {(r,c) for r,c in block_cells if r <= split_row}
        bottom_cells = {(r,c) for r,c in block_cells if r > split_row}
        return (subdivide_block_into_lots(top_cells, rng, min_lot_width, min_lot_height) +
                subdivide_block_into_lots(bottom_cells, rng, min_lot_width, min_lot_height))

    elif not split_horizontal and width >= min_lot_width * 2:
        # Split along a column line
        mid = (c_min + c_max) // 2
        offset = int(rng.uniform(-width * 0.2, width * 0.2))
        split_col = mid + offset
        split_col = max(c_min + min_lot_width, min(c_max - min_lot_width, split_col))

        left_cells  = {(r,c) for r,c in block_cells if c <= split_col}
        right_cells = {(r,c) for r,c in block_cells if c > split_col}
        return (subdivide_block_into_lots(left_cells, rng, min_lot_width, min_lot_height) +
                subdivide_block_into_lots(right_cells, rng, min_lot_width, min_lot_height))

    else:
        # Cannot split in the preferred direction; try the other
        return [block_cells]
```

**Note:** For non-rectangular blocks (irregular outlines), compute the bounding box and treat cells outside the block outline as excluded. For our mostly-rectangular tile grid, blocks produced by cardinal road grids will be nearly rectangular.

---

### 7.3 Park Placement

Convert qualifying blocks to park tiles after lot subdivision.

```python
PARK_MAX_AREA = 100   # cells — blocks too large to subdivide usefully
PARK_MIN_AREA = 4     # cells — blocks too small to build on
PARK_RNG_CHANCE = {
    'CBD': 0.03,
    'MIDTOWN': 0.07,
    'RESIDENTIAL': 0.12,
}

def assign_parks(blocks, grid, zone_map, rng):
    """
    blocks: list of sets of (row, col) tuples (from detect_blocks)
    grid: 2D cell array (mutable)
    zone_map: dict (row,col) -> zone string
    rng: seeded random.Random
    """
    for block in blocks:
        area = len(block)
        is_park = False

        # Size-based rules
        if area > PARK_MAX_AREA or area < PARK_MIN_AREA:
            is_park = True

        # Zone-weighted stochastic rule
        if not is_park:
            sample_cell = next(iter(block))
            zone = zone_map.get(sample_cell, 'RESIDENTIAL')
            chance = PARK_RNG_CHANCE.get(zone, 0.07)
            # Boost park chance for blocks far from any highway
            min_hw_dist = min_distance_to_highway(sample_cell, grid)
            if min_hw_dist > 8:
                chance *= 1.5
            if rng.random() < chance:
                is_park = True

        if is_park:
            for (r, c) in block:
                grid[r][c].tile_type = PARK

def min_distance_to_highway(cell, grid):
    """Chebyshev distance from cell to nearest highway tile (approximate)."""
    r0, c0 = cell
    # Sample a 16-cell radius — sufficient for our map scale
    for radius in range(1, 17):
        for dr in range(-radius, radius+1):
            for dc in range(-radius, radius+1):
                if abs(dr) == radius or abs(dc) == radius:
                    r, c = r0+dr, c0+dc
                    if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                        if grid[r][c].tile_type == HIGHWAY:
                            return radius
    return 16
```

---

### 7.4 Density Gradient (Building Height Score)

Assigns a `density_score` (0.0–1.0) to each block, used downstream by the building generation phase to select tile variants or building heights.

```python
def compute_density_scores(blocks, zone_map, grid, highway_cells):
    """
    Returns dict: block_id -> density_score (float 0.0–1.0)
    Higher = denser/taller buildings.
    """
    ZONE_BASE = {'CBD': 0.85, 'MIDTOWN': 0.55, 'RESIDENTIAL': 0.25}
    scores = {}

    for i, block in enumerate(blocks):
        if not block:
            continue

        # 1. Zone base score
        sample = next(iter(block))
        zone = zone_map.get(sample, 'RESIDENTIAL')
        base = ZONE_BASE.get(zone, 0.25)

        # 2. Highway proximity bonus (closer = denser)
        centroid_r = sum(r for r,c in block) / len(block)
        centroid_c = sum(c for r,c in block) / len(block)
        min_hw_dist = _nearest_highway_distance(centroid_r, centroid_c, highway_cells)
        # Normalize: 0 cells away = +0.15, 10+ cells away = 0 bonus
        hw_bonus = max(0.0, 0.15 * (1.0 - min_hw_dist / 10.0))

        # 3. Block size penalty (very large blocks are parks or industrial, not dense)
        size_penalty = min(0.2, len(block) / 200.0)

        score = base + hw_bonus - size_penalty
        scores[i] = max(0.0, min(1.0, score))

    return scores

def _nearest_highway_distance(r, c, highway_cells):
    """Euclidean distance from point (r,c) to nearest highway cell."""
    if not highway_cells:
        return 999.0
    return min(
        ((r - hr)**2 + (c - hc)**2)**0.5
        for hr, hc in highway_cells
    )
```

**Usage:** `density_score > 0.7` → high-rise tile variants; `0.4–0.7` → mid-rise; `< 0.4` → low-rise / detached.

---

## 8. Prioritized Recommendations

Sorted by **visual impact / implementation effort** ratio (best ROI first).

| # | Feature | Algorithm | Est. LOC | Difficulty | Visual Impact |
|---|---|---|---|---|---|
| 1 | Block detection | BFS flood fill (Section 7.1) | 50 | Low | High — enables everything below |
| 2 | Lot subdivision | Alternating axis split (Section 7.2) | 80 | Low | High — parcels give the city structure |
| 3 | Park placement | Size + zone threshold (Section 7.3) | 60 | Low | High — breaks building monotony |
| 4 | Density gradient score | Zone + highway proximity (Section 7.4) | 70 | Low | High — drives building height variation |
| 5 | Spatially-correlated dropout | Replace flat dropout with `base_rate × (1 - noise)` | 30 | Low | Medium-High — organic neighborhood feel |
| 6 | Dead-end cul-de-sacs | Extend dropped connectors 1–2 tiles then terminate | 40 | Low | Medium — suburban authenticity |
| 7 | CBD civic anchor | Mark centroid cell, boost connector density nearby | 35 | Low | Medium — focal point landmark |
| 8 | Irregular block sizes | Noise-offset connector spacing (Section 6.1) | 25 | Low | Medium — removes grid rigidity |
| 9 | Park seeding in Residential | Zone-weighted stochastic park (Section 4.2) | 20 | Low | Medium — green space realism |
| 10 | WFC visual post-pass | Variant selection on road tile visual layer | 180 | Medium | Medium — surface variety |
| 11 | CBD radial road bias | Rotate connector preference toward CBD centroid | 60 | Medium | Medium — hub-and-spoke feel |
| 12 | Staggered grid offset | Alternate connector row x-offsets (Section 6.1) | 45 | Low | Low-Medium — subtle organic offset |

**Recommended sprint order:** Items 1–4 together form the "block + lot + park + density" pipeline and should be implemented as a single Phase 6 in the existing architecture. Items 5–9 are parameter tweaks to existing phases. Items 10–12 are quality-of-life polish for a later sprint.

---

## 9. Integration Notes for Existing Architecture

The existing pipeline produces a `grid` of `MapCell` objects with a `tile_type` attribute and a `zone` attribute (set during Phase 2 Chebyshev distance assignment). The recommended Phase 6 integration:

```python
# In map_generator.py, after Phase 5 (sidewalks):
from map_builder.phases.block_subdivision import (
    detect_blocks, subdivide_block_into_lots,
    assign_parks, compute_density_scores
)

def _phase_6_blocks_and_lots(self):
    blocks = detect_blocks(self.grid, self.width, self.height)
    highway_cells = {(r,c) for r in range(self.height)
                          for c in range(self.width)
                          if self.grid[r][c].tile_type == HIGHWAY}
    lots = []
    for block in blocks:
        lots.extend(subdivide_block_into_lots(block, self.rng))
    assign_parks(blocks, self.grid, self.zone_map, self.rng)
    self.density_scores = compute_density_scores(
        blocks, self.zone_map, self.grid, highway_cells
    )
    self.lots = lots
```

All algorithms are `O(W×H)` or better and add negligible generation time on 64×48–96×72 maps.

---

## Sources

- [Parish & Müller 2001 — Procedural Modeling of Cities (ACM DL)](https://dl.acm.org/doi/10.1145/383259.383292)
- [Parish & Müller 2001 — Procedural Modeling of Cities (ResearchGate)](https://www.researchgate.net/publication/220720591_Procedural_Modeling_of_Cities)
- [Chen et al. 2008 — Interactive Procedural Street Modeling (PDF)](https://www.sci.utah.edu/~chengu/street_sig08/street_sig08.pdf)
- [Chen et al. 2008 — Project Page](https://www.sci.utah.edu/~chengu/street_sig08/street_project.htm)
- [Vanegas et al. 2012 — Procedural Generation of Parcels in Urban Modeling](https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg2012.pdf)
- [josauder/procedural_city_generation (GitHub)](https://github.com/josauder/procedural_city_generation)
- [josauder — Documentation](https://josauder.github.io/procedural_city_generation/)
- [t-mw/citygen (GitHub)](https://github.com/t-mw/citygen)
- [t-mw/citygen-godot (GitHub)](https://github.com/t-mw/citygen-godot)
- [mxgmn/WaveFunctionCollapse (GitHub)](https://github.com/mxgmn/WaveFunctionCollapse)
- [Procedural Generation For Dummies: Lot Subdivision — Martin Evans](https://martindevans.me/game-development/2015/12/27/Procedural-Generation-For-Dummies-Lots/)
- [Recursive Subdivision Variants — BorisTheBrave](https://www.boristhebrave.com/2021/08/14/recursive-subdivision-variants/)
- [Wave Function Collapse Tips and Tricks — BorisTheBrave](https://www.boristhebrave.com/2020/02/08/wave-function-collapse-tips-and-tricks/)
- [Infinite Procedurally Generated City with WFC — Marian42](https://marian42.de/article/wfc/)
- [How Townscaper Works — Game Developer](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making)
- [Procedural City Generation — tmwhere](https://www.tmwhere.com/city_generation.html)
- [A Survey of Procedural Techniques for City Generation (PDF)](https://arrow.tudublin.ie/cgi/viewcontent.cgi?article=1097&context=itbj)
