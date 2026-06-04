# Open World Chunk System Specification
**Status:** Draft v1.0  
**Date:** 2026-05-29  
**Author:** World Architecture Director  
**Engine:** mapping_algorithm_cpp.v3 / MapGenerator C++ backend

---

## Notation

- **SPECIFIED** — must be implemented exactly as written; changing this breaks cross-chunk compatibility
- **SUGGESTED** — the recommended approach; iteration is acceptable as long as the contract to adjacent systems is preserved
- **OPEN** — deliberately unresolved; a decision is needed before implementation

---

## 1. Scale Definition

### 1.1 Tile Size

**SPECIFIED**

One tile = **2 metres** of in-game distance (gameplay feel, not simulation accuracy).

Rationale: at this scale a 96×72-cell chunk (the current default `MapConfig`) covers roughly 192 m × 144 m, which is a normal city block cluster. A highway strip visible at the chunk edge reads as a real road, and individual building footprints remain legible in isometric pixel art at 1:1 tile resolution.

### 1.2 World Dimensions

**SPECIFIED**

| Parameter | Value |
|---|---|
| Chunk size | 256 × 256 cells |
| World grid | 8 chunks wide × 6 chunks tall |
| World size in cells | 2048 × 1536 cells |
| World size in metres | 4096 m × 3072 m (~12.6 km²) |
| Target gameplay feel | ~quarter of GTA5 (~20 km²) |

The raw area (~12.6 km²) is smaller than the 20 km² target because an isometric pixel art world with foot traversal feels larger than its metric equivalent — a player's effective field of view covers only a fraction of the screen's real distance, making traversal feel longer than the numbers suggest. This is intentional.

Note: the current `MapConfig` defaults to 96×72 cells. For the open world, every chunk will be instantiated with `width = 256, height = 256`. The existing `MAX_MAP_DIMENSION = 512` cap in `map_generator.cpp` already allows this.

### 1.3 Traversal Times (SUGGESTED)

Foot speed: ~3 tiles/second (6 m/s in-game — brisk walk for an action RPG).

| Route | Distance | Time on foot |
|---|---|---|
| One chunk (256 tiles) | 512 m | ~1 min 25 sec |
| World width (2048 tiles) | 4096 m | ~11 min 20 sec |
| World diagonal | ~2560 tiles | ~14 min |
| Full perimeter | ~6208 tiles | ~35 min |

A player who walks in a straight line across the widest axis takes ~11 minutes. Realistic play (roads, exploration, encounters) should feel like 30–50 minutes of traversal time, satisfying the "large open world" target without approaching GTA5's scale.

---

## 2. Chunk System Architecture

### 2.1 Definitions

**SPECIFIED**

```
CHUNK_W = 256   // cells per chunk, X axis (col)
CHUNK_H = 256   // cells per chunk, Y axis (row)
WORLD_CX = 8    // number of chunks, X axis
WORLD_CY = 6    // number of chunks, Y axis
```

A chunk is identified by its chunk-grid coordinates `(cx, cy)` where:
- `cx` ∈ [0, WORLD_CX − 1] = [0, 7]
- `cy` ∈ [0, WORLD_CY − 1] = [0, 5]
- `(0, 0)` is the **north-west** corner of the world

### 2.2 Coordinate Mapping

**SPECIFIED**

Converting world-cell coordinates `(wx, wy)` to chunk + local:

```cpp
// Given world cell (wx, wy):
int cx = wx / CHUNK_W;          // chunk column
int cy = wy / CHUNK_H;          // chunk row
int lx = wx % CHUNK_W;          // local col within chunk
int ly = wy % CHUNK_H;          // local row within chunk
```

Converting back:

```cpp
int wx = cx * CHUNK_W + lx;
int wy = cy * CHUNK_H + ly;
```

Within a chunk, the `MapGrid` convention is `at(row, col)` where `row = ly` and `col = lx`.

### 2.3 Chunk Seed Derivation

**SPECIFIED**

```cpp
// mix_u32 is the same function already in map_generator.cpp:
//   x ^= x >> 16;  x *= 0x7feb352dU;
//   x ^= x >> 15;  x *= 0x846ca68bU;
//   x ^= x >> 16;

uint32_t chunk_seed(uint32_t world_seed, int cx, int cy) {
    uint32_t h = world_seed;
    h ^= static_cast<uint32_t>(cx) * 0x9e3779b9U;
    h ^= static_cast<uint32_t>(cy) * 0x517cc1b7U;
    return mix_u32(h);
}
```

This is the sole seed derivation formula. Any other formula produces a different world for the same master seed — do not deviate.

`MapConfig::master_seed` for a chunk is set to `chunk_seed(world_seed, cx, cy)`.

### 2.4 MapConfig Construction per Chunk

**SPECIFIED** (structure); **SUGGESTED** (field values)

```cpp
MapConfig config_for_chunk(uint32_t world_seed, int cx, int cy) {
    MapConfig cfg;
    cfg.width          = CHUNK_W;
    cfg.height         = CHUNK_H;
    cfg.master_seed    = chunk_seed(world_seed, cx, cy);
    cfg.city_profile   = world_profile_for_chunk(cx, cy);  // §3
    cfg.coast_side     = world_coast_for_chunk(cx, cy);    // §5
    // highway boundary constraints applied after construction — §4
    return cfg;
}
```

All other `MapConfig` fields (`connector_density`, `avenue_spacing`, etc.) are resolved from the `city_profile` by the existing `rules_for_profile()` logic inside `MapGenerator`. No new fields are needed on `MapConfig` for the world system.

---

## 3. World-Level Zone Layout

### 3.1 Zone Assignment per Chunk

**SPECIFIED**

The world has a single global zone structure that determines each chunk's dominant character. This is expressed by selecting the `city_profile` string passed to `MapConfig`.

```
World grid (cx, cy) — zone layout (0,0 = NW corner):

  cx:   0     1     2     3     4     5     6     7
cy 0: [ RES ] [RES ] [MID ] [CBD ] [CBD ] [MID ] [RES ] [RES ]
cy 1: [ RES ] [MID ] [CBD ] [CBD ] [CBD ] [CBD ] [MID ] [RES ]
cy 2: [ RES ] [MID ] [CBD ] [CBD ] [CBD ] [CBD ] [MID ] [RES ]
cy 3: [ RES ] [MID ] [CBD ] [CBD ] [CBD ] [CBD ] [MID ] [RES ]
cy 4: [ RES ] [MID ] [CBD ] [MID ] [MID ] [CBD ] [MID ] [RES ]
cy 5: [ RES ] [RES ] [MID ] [MID ] [MID ] [MID ] [RES ] [RES ]
```

- **CBD** — city centre chunks (columns 2–5, rows 1–4, with degradation at south edge)
- **MID** — midtown / transition ring
- **RES** — outer residential / low-density

### 3.2 `world_zone_for_chunk` Function Spec

**SPECIFIED**

```cpp
enum class WorldZone { CBD, Midtown, Residential };

WorldZone world_zone_for_chunk(int cx, int cy,
                                int world_cx = WORLD_CX,
                                int world_cy = WORLD_CY) {
    // Normalise to [0.0, 1.0] from the world centre
    float nx = std::abs(cx - (world_cx - 1) / 2.0f) / (world_cx / 2.0f);
    float ny = std::abs(cy - (world_cy - 1) / 2.0f) / (world_cy / 2.0f);
    float dist = std::max(nx, ny);  // Chebyshev distance from centre

    if (dist <= 0.30f) return WorldZone::CBD;
    if (dist <= 0.65f) return WorldZone::Midtown;
    return WorldZone::Residential;
}
```

### 3.3 Zone → City Profile Mapping

**SPECIFIED**

```cpp
std::string world_profile_for_chunk(int cx, int cy) {
    switch (world_zone_for_chunk(cx, cy)) {
        case WorldZone::CBD:
            // Alternate between manhattan and paris for texture variety.
            // Use chunk parity so adjacent chunks differ.
            return ((cx + cy) % 2 == 0) ? "manhattan" : "paris_haussmann";
        case WorldZone::Midtown:
            return "generic_dense";
        case WorldZone::Residential:
            return "london_organic";
    }
}
```

The `barcelona_eixample` profile is currently reserved for a special district — SUGGESTED for a named neighbourhood injected into one midtown chunk (see §10, open question on landmark distribution).

### 3.4 Local Zone Override

**SPECIFIED**

Each `MapGenerator` instance still runs its own internal `generate_zones()` using the CBD/Midtown/Residential radii. The world zone assignment governs the *profile* and *coast* fed to the generator; it does NOT suppress the per-chunk zone subdivision. A CBD chunk still has its own internal neighbourhood gradient (core CBD → midtown → residential edge). This is correct and desirable — it gives texture at the micro scale.

---

## 4. Cross-Chunk Road Continuity

### 4.1 Highway Grid

**SPECIFIED**

A world-level highway grid is computed before any chunk is generated. This grid defines which chunk boundaries carry a highway connection.

```
Highway columns (east-west highways, running along rows of chunks):
  Every 3 chunk rows → a horizontal highway band.
  Highway band rows: cy = 1, cy = 4

Highway rows (north-south highways, running along columns of chunks):
  Every 2 chunk columns → a vertical highway band.
  Highway band cols: cx = 1, cx = 3, cx = 5, cx = 7 (but cx=7 is world edge, skip)
  Effective: cx = 1, cx = 3, cx = 5
```

These values are **derived from the world seed** so they are stable, not hardcoded. The derivation:

```cpp
// Returns the set of cx values that carry a N-S through-highway
std::vector<int> highway_ns_columns(uint32_t world_seed) {
    // Fixed structural columns at roughly 1/4, 1/2, 3/4 of world width
    // Perturb slightly with world_seed so no two worlds look identical
    uint32_t h = mix_u32(world_seed ^ 0xDEADBEEFU);
    int offset = static_cast<int>(h % 2);  // 0 or 1 tile shift, chunk-column units
    return { 1 + offset, 3, 5 + offset };  // 3 N-S highways
}

std::vector<int> highway_ew_rows(uint32_t world_seed) {
    uint32_t h = mix_u32(world_seed ^ 0xBEEFCAFEU);
    int offset = static_cast<int>(h % 2);
    return { 1 + offset, 4 };              // 2 E-W highways
}
```

### 4.2 Chunk Boundary Protocol

**SPECIFIED**

When two horizontally adjacent chunks share a boundary (chunk `(cx, cy)` on the left, chunk `(cx+1, cy)` on the right), the east edge of the left chunk and the west edge of the right chunk must agree on road presence and category.

**Rule:** if the boundary falls on a highway column (`cx` is in `highway_ns_columns`), both chunks must have a `RoadCategory::Highway` cell at the boundary column (col = 255 in the left chunk, col = 0 in the right chunk) for every row that the highway passes through.

Implementation approach (SUGGESTED — exact stitching logic is an open implementation detail):
1. After generating a chunk, read its east/west/north/south edge road layout.
2. Generate the adjacent chunk with an explicit boundary constraint: force `RoadCategory::Highway` at the boundary cells where the world highway grid requires it, before calling `generate_connectors()`.
3. The `MapGenerator::set_road()` private method already handles this; a pre-seeding pass sets those cells before `generate_highways()` runs.

Connector roads (`RoadCategory::Connector`) do NOT need to be continuous across chunk boundaries. A connector road may end at the chunk boundary and the adjacent chunk generates its own connector network fresh.

### 4.3 Visual Continuity at Non-Highway Boundaries

**SUGGESTED**

At non-highway chunk boundaries, there will be visible seams where connector road patterns do not align. To mitigate:
- Keep a 4-cell-wide "seam buffer" on each chunk edge. Roads in this buffer should favour straight (non-diagonal, non-organic) patterns.
- The `connector_organic` parameter should be forced to `0.0` for cells within 4 columns/rows of a chunk boundary.

This is SUGGESTED — it can be deferred to the visual polish pass.

---

## 5. Cross-Chunk River and Coastline

### 5.1 Coastline Assignment

**SPECIFIED**

```cpp
CoastSide world_coast_for_chunk(int cx, int cy) {
    bool north_edge = (cy == 0);
    bool south_edge = (cy == WORLD_CY - 1);
    bool west_edge  = (cx == 0);
    bool east_edge  = (cx == WORLD_CX - 1);

    // Corner precedence: north/south beats east/west
    if (north_edge) return CoastSide::North;
    if (south_edge) return CoastSide::South;
    if (west_edge)  return CoastSide::West;
    if (east_edge)  return CoastSide::East;
    return CoastSide::None;
}
```

Interior chunks always get `CoastSide::None`. Edge chunks get a single directional coast. Corner chunks (e.g., `(0,0)`) receive North because north takes precedence — the corner chunk shows the north coast, not the west.

The `coast_coverage` and `coast_noise_scale` fields on `MapConfig` are left at defaults for all coast chunks. Do not vary these per-chunk — visual consistency across the world edge is more important than variety.

### 5.2 Rivers

**SPECIFIED (system contract)**; **SUGGESTED (implementation)**

Rivers are world-level features. A river is defined as a spline in world-cell coordinates. Each chunk that the river spline intersects clips the spline to its local cell space and uses it as input to `MapGenerator::generate_river()`.

World river contract:
- A river that enters a chunk from the west edge **must exit** from either the east or south edge of the same chunk. No dead-end rivers within a chunk (they must have an outlet).
- Rivers do not branch across chunk boundaries — a river has exactly one entry edge and one exit edge per chunk it crosses.

World-level river generation (SUGGESTED):

```
1. Roll N rivers per world (SUGGESTED: 1–3, derived from world_seed)
2. Each river starts at a world edge cell (north or west border)
3. River path is a piecewise-linear spline in world-cell coordinates,
   generated once, stored as a list of (wx, wy) waypoints
4. For each chunk the river crosses, pass the clipped entry/exit cells
   as boundary constraints to MapConfig (new fields needed — see §10)
5. MapGenerator respects these entry/exit cells when calling generate_river()
```

MapConfig currently has no river boundary fields. Adding them is required for this feature. OPEN — see §10.

### 5.3 River-Free Interior

**SPECIFIED**

CBD chunks (world zone = CBD) must not contain rivers. If a world-level river spline intersects a CBD chunk, that river segment is suppressed for that chunk. The river "goes underground" (implied tunnel) and resumes in the next non-CBD chunk.

---

## 6. Chunk Loading Strategy

### 6.1 Active Zone

**SPECIFIED**

At any moment the runtime maintains three tiers of chunk state:

| Tier | Size | Content | Memory target |
|---|---|---|---|
| **Rendered** | 1×1 chunk | Full `MapGrid` + `DesignBlueprint` | ~8 MB |
| **Active** | 3×3 chunks | Full `MapGrid` + `DesignBlueprint` | ~72 MB |
| **Pre-loaded** | 5×5 chunks | Zone + elevation + highway edges only | ~5 MB |

The 3×3 active zone is centred on the chunk the player currently occupies. All 9 chunks must be fully generated and in memory before the player can move into the outer ring.

### 6.2 Load Triggers

**SUGGESTED**

- When the player crosses into a new chunk, the active zone re-centres. The 4 new chunks entering the 3×3 ring must be generated before the player can reach their inner edge.
- Generation budget: any single chunk must complete in <100ms (see §9). The 4 new chunks entering the ring have until the player walks ~128 cells (~43 seconds at foot speed) to be ready.
- Pre-loaded chunks (5×5 ring, zone/elevation only) are generated asynchronously at <10ms each.

### 6.3 Render Distance

**SPECIFIED**

The renderer displays at most **1 chunk (256×256 cells)** at normal zoom. The camera always sits within the currently occupied chunk. Zoom-out beyond 1-chunk view is **not required** by this spec — it is OPEN (see §10).

---

## 7. Seeding Protocol (Canonical Reference)

This section is the authoritative specification. If any other document or source file contradicts this, this document takes precedence.

### 7.1 World Seed

**SPECIFIED**

```cpp
using WorldSeed = uint32_t;
```

The master seed is a single `uint32_t`. It is the only external input to the entire world generation pipeline. Given the same `WorldSeed`, the entire world — every chunk, every road, every building — is reproducible.

Persistence: the `WorldSeed` is stored in the save file. The cache format (see §9) uses it as part of the cache key.

### 7.2 Chunk Seed Formula

**SPECIFIED**

```cpp
uint32_t chunk_seed(WorldSeed world_seed, int cx, int cy) {
    uint32_t h = world_seed;
    h ^= static_cast<uint32_t>(cx) * 0x9e3779b9U;
    h ^= static_cast<uint32_t>(cy) * 0x517cc1b7U;
    return mix_u32(h);
}
```

Where `mix_u32` is identical to the function in `mapping_algorithm/cpp/src/map_generator.cpp`:

```cpp
uint32_t mix_u32(uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}
```

This function must be copied verbatim (or shared via a header) — do not use a different finaliser.

### 7.3 Sub-System Salt Values

**SPECIFIED**

Inside each chunk, the existing salt constants in `map_generator.cpp` remain unchanged:

```cpp
constexpr uint32_t SALT_COAST     = 0xAB1234;
constexpr uint32_t SALT_RIVER     = 0xC0A57EA7;
constexpr uint32_t SALT_ELEVATION = 0xE1E2E3E4;
constexpr uint32_t SALT_HIGHWAY   = 0xCD5678;
constexpr uint32_t SALT_CONNECTOR = 0xEF9ABC;
constexpr uint32_t SALT_PARKS     = 0xA1B2C3;
constexpr uint32_t SALT_BUILDINGS = 0xB1C2D3;
```

The world-level systems (highway grid, river spline) use their own salts derived from `world_seed` directly, not from any chunk seed:

```cpp
constexpr uint32_t SALT_WORLD_HIGHWAY = 0xDEADBEEFU;
constexpr uint32_t SALT_WORLD_RIVER   = 0xBEEFCAFEU;
```

### 7.4 City Profile Assignment

**SPECIFIED** (mapping); **SUGGESTED** (future extension)

```
WorldZone::CBD       → "manhattan"  or  "paris_haussmann"  (alternating by (cx+cy) parity)
WorldZone::Midtown   → "generic_dense"
WorldZone::Residential → "london_organic"
```

The `barcelona_eixample` profile is not assigned automatically. It is reserved for manually curated named districts (OPEN — §10).

### 7.5 Coast Side Assignment

Per §5.1 — edge chunks get a directional coast, interior chunks get `CoastSide::None`.

---

## 8. World Generation Order

**SPECIFIED** (order of steps); **SUGGESTED** (within each step)

```
Step 1 — World Seed
  Input:  WorldSeed (from new game dialog, save file, or CLI flag)

Step 2 — World Highway Grid
  Compute highway_ns_columns(world_seed) and highway_ew_rows(world_seed).
  Store as world-level metadata. This data is deterministic and tiny (~20 integers).

Step 3 — World River Spline(s) [SUGGESTED — may be deferred]
  Compute N river splines in world-cell coordinates.
  For each spline, record which chunks it crosses and the entry/exit cell indices.

Step 4 — Chunk Config Construction (per chunk, lazy or batch)
  For each (cx, cy) needed:
    a. Compute chunk_seed(world_seed, cx, cy)
    b. Look up world_zone_for_chunk → city_profile
    c. Look up world_coast_for_chunk → coast_side
    d. Apply highway boundary constraints from Step 2 (force road cells at edges)
    e. Apply river boundary constraints from Step 3 (if rivers implemented)
    f. Construct MapConfig

Step 5 — Chunk Generation
  For each MapConfig from Step 4:
    Instantiate MapGenerator(config), call generate().
  This step is parallelisable — each chunk is independent given its MapConfig.

Step 6 — Boundary Stitch
  For each pair of adjacent chunks:
    a. Verify highway cells at shared boundary match on both sides.
    b. If mismatch: apply post-generation fixup (overwrite boundary cells to Highway).
    c. Log any stitching overrides for debugging.

Step 7 — Cache Write
  Serialise each chunk's DesignBlueprint to JSON.
  Cache key: { world_seed, cx, cy }  (see §9)
```

Steps 4–5 are safe to parallelise across chunks using a thread pool. Steps 2 and 3 must complete before any Step 4 begins.

---

## 9. Performance Budget

### 9.1 Generation Time

**SPECIFIED**

| Target | Value |
|---|---|
| Single chunk generation | < 100 ms |
| 9-chunk active zone (cold, sequential) | < 900 ms |
| 9-chunk active zone (parallel, 4 threads) | < 300 ms |
| Pre-load tier (25 chunks, zone+elevation only) | < 250 ms total |

Basis: the current `MapGenerator` generates a 96×72 chunk in <5ms. A 256×256 chunk is approximately 12× more cells. Assuming roughly linear scaling (which is pessimistic — highways and blocks scale sub-linearly), a 256×256 chunk should complete in ~30–60ms. The 100ms budget has ~2× headroom.

If profiling shows the 256×256 chunk exceeds 100ms, reduce to **192×192** cells per chunk. This reduces the world to 1536×1152 cells total but keeps the feel target intact (traversal times reduce proportionally). Do not reduce below 192×192.

### 9.2 Memory Budget

**SUGGESTED**

| Object | Size estimate | Count (active zone) | Total |
|---|---|---|---|
| `MapCell` struct | ~120 bytes | 256×256×9 = 589,824 | ~68 MB |
| `DesignBlueprint` (roads, lots, buildings) | ~2 MB | 9 | ~18 MB |
| Pre-load tier (zone+elevation only, ~8 bytes/cell) | ~0.5 MB | 25 | ~12 MB |
| **Total active** | | | **~98 MB** |

This is within a 128 MB budget for world data. If `MapCell` is larger (due to `std::string` members), consider replacing `std::string` fields with interned enum + string-table indices for the in-memory representation. The JSON serialisation layer is unaffected.

### 9.3 Cache Format

**SPECIFIED**

Cache files use the existing `deployable_city_map.v2` JSON schema (same as `exports/city_seed_42.json`).

Cache key components:
```json
{
  "world_seed": 1234567890,
  "chunk_x": 3,
  "chunk_y": 2,
  "chunk_size": 256,
  "algorithm_version": "mapping_algorithm_cpp.v3"
}
```

Cache filename convention: `chunk_{world_seed}_{cx}_{cy}.json`  
Cache directory: `exports/chunks/`

Cache invalidation: if `algorithm_version` in the cached file does not match the current binary's version string, the cache entry is stale and must be regenerated.

---

## 10. Open Questions

These are deliberately unresolved. A decision is required before the relevant system is implemented.

### 10.1 Chunk Transition — Seamless Streaming vs. Load Screen

**OPEN**

Two viable approaches:

A. **Seamless streaming** — the 3×3 active zone expands as the player walks. The engine continuously generates and discards chunks in the background. No loading screen. Requires robust background thread management and the 4-thread parallelism budget from §9.1.

B. **Discrete zone transition** — when the player crosses a chunk boundary, a brief (1–2 second) load screen appears while the new ring generates. Simpler to implement; breaks immersion.

Decision needed before implementing the chunk loading manager.

### 10.2 Landmark Distribution — World vs. Per-Chunk

**OPEN**

The current `MapGenerator` places landmarks (town hall, station, hospital, police, school) per-chunk using per-chunk seeded randomness. In an open world, certain landmarks should be unique world-wide (e.g., only one main train station, one city hall).

Options:

A. **World-level landmark registry** — the world generator pre-assigns landmark types to specific chunk coordinates. Those chunks are told which landmark to place via a new `MapConfig` field, overriding the per-chunk random placement.

B. **Post-hoc deduplication** — generate all chunks normally, then scan the cache and flag duplicate landmark types. Keep the closest-to-centre instance, mark others as suppressed.

C. **Tile-role only, no world-unique landmarks** — treat all landmarks as local flavour. Accept that there will be multiple train stations. The world "feels" like a city with multiple transit hubs.

### 10.3 Economy and Faction Zones

**OPEN**

The `ZoneId` enum (CBD / Midtown / Residential) already exists at the cell level. It is not yet connected to any economy or faction system.

Questions to resolve:

- Does the world-zone assignment (§3) feed directly into faction territory definitions?
- Are faction territories fixed (derived from world seed) or dynamic (player-influenced)?
- Should `MapCell::encounter_chance` be modulated by world zone, or only by per-chunk density score?

### 10.4 River Boundary Fields on MapConfig

**OPEN**

Section §5.2 requires that a chunk's `MapConfig` specify the entry and exit cells for any rivers that cross its boundary. `MapConfig` currently has no such fields. Two fields need to be added (or an alternative mechanism designed):

```cpp
// Proposed additions to MapConfig — NOT yet specified:
struct RiverBoundaryConstraint {
    int entry_edge;   // 0=North, 1=East, 2=South, 3=West
    int entry_cell;   // column (for N/S edges) or row (for E/W edges)
    int exit_edge;
    int exit_cell;
};
std::optional<RiverBoundaryConstraint> river_constraint;
```

This must be agreed upon before the river system is implemented.

### 10.5 Zoom-Out and Mini-Map

**OPEN**

Section §6.3 specifies a 1-chunk render distance at normal zoom. Two unresolved questions:

- Is a zoom-out mode (showing 2×2 or 3×3 chunks) required? If so, what is the performance budget for rendering multiple chunks simultaneously?
- The mini-map UI will likely need a low-resolution representation of the full world. How is this generated — pre-rendered at world-gen time, or derived from the zone layout alone?

---

## Appendix A: MapConfig Fields Reference

For convenience, the full `MapConfig` struct as of `mapping_algorithm_cpp.v3`:

```cpp
struct MapConfig {
    int width           = 96;                      // SET TO 256 for open world chunks
    int height          = 72;                      // SET TO 256 for open world chunks
    uint32_t master_seed = 1;                      // SET BY chunk_seed()
    std::string city_profile = "generic_dense";    // SET BY world_profile_for_chunk()

    CoastSide coast_side       = CoastSide::None;  // SET BY world_coast_for_chunk()
    double coast_coverage      = 0.24;
    double coast_noise_scale   = 3.5;
    int coast_smoothing_passes = 2;

    int highway_ns_min      = 2;
    int highway_ns_max      = 5;
    int highway_ew_min      = 0;
    int highway_ew_max      = 3;
    double highway_organic  = 0.3;
    double connector_organic = 0.08;

    double connector_density = 0.65;
    int connector_spacing    = 8;
    int avenue_spacing       = 18;
    int min_block_depth      = 2;
    double connector_turn_bias = 0.08;
    int roundabout_count     = 8;
    int diagonal_streets     = 2;
    int sidewalk_depth       = 1;
    double sidewalk_damage_rate = 0.15;
};
```

Fields marked "SET BY" above are controlled by the world system. All other fields use their defaults unless the `city_profile` resolution (inside `rules_for_profile()`) modifies them.

---

## Appendix B: Known City Profiles

| ID | Character | World Zone |
|---|---|---|
| `manhattan` | Dense grid, long avenues, diagonal streets, high organic | CBD (even parity) |
| `paris_haussmann` | Boulevard grid, moderate density | CBD (odd parity) |
| `generic_dense` | Default dense urban | Midtown |
| `london_organic` | Low organic, irregular blocks | Residential |
| `barcelona_eixample` | Octagonal block grid | Reserved — named district |

---

*End of specification.*
