# Studio Output — Sprint 3: Terrain-First Roads, City Archetypes, Organic Network

Date: 2026-05-29

---

## Director Team

| Role | Responsibility |
|---|---|
| Executive Producer | Orchestration, algorithm analysis, acceptance criteria, this document |
| Lead C++ Programmer | A1 terrain-following highways, A2 city archetypes + ring roads, A3 roundabouts, A4 connector turn bias, A5 CBD center offset + smoke tests |
| World Architecture Director | Archetype system design consultation, ring road radius specification |
| QA / Test Director | 78/78 smoke verification, build gate confirmation, terrain routing check, map variation check |

All staff worked in parallel. Lead Programmer delivered in a worktree-isolated branch; merged after full smoke pass.

---

## Mission

Third analysis sprint against ProbableTrain/MapGenerator. Sprint 2 delivered elevation-influenced buildings, block perimeter facing tags, highway junction marking, and the WorldGenerator class. Sprint 3 delivers:

1. **Terrain-following highway routing** — elevation DP avoids hilltops, follows valleys (Defect 1 fix)
2. **City archetype system** — Grid / Radial / Organic, seed-determined via `mix_u32(seed ^ 0x3A7F9B2C) % 3`
3. **Ring roads** — circular orbital road around CBD center for Radial archetype
4. **Roundabouts** — connector-ring cells at highway×highway junctions
5. **connector_turn_bias** — sign-change amplification for S-curves and hooks on connector streets
6. **CBD center offset** — seeded ±5% offset for structural map variety
7. **78/78 smoke checks** — +2 new checks: terrain routing verification, map variation verification

---

## Algorithm Comparison Update

### Sprint 3 Additions

| Feature Added | Implementation |
|---|---|
| Terrain-following highway routing | Elevation DP: per-row/col ±5-cell scan, cost = elev×4 + lateral + drift_pen + FBM bonus |
| City archetype system | `archetype_ = mix_u32(seed ^ 0x3A7F9B2C) % 3` → Grid=0, Radial=1, Organic=2 |
| Ring road | `generate_ring_road()`: radius=28% of min(H,W), 2π×radius×2.5 steps, stair-step fill |
| Roundabouts | At highway cells with 3+ highway neighbours: 8-cell connector ring, budget=roundabout_count |
| connector_turn_bias | Sign-flip detection on FBM noise; drift×(1 + bias×3) when direction reverses |
| CBD center offset | `decision01(seed, 77/88, 99/77, SALT_ELEVATION)` ×10%×dim, clamped [20%, 80%] |

### Feature-by-Feature Matrix (Updated Sprint 3)

| Feature | Ours | ProbableTrain |
|---|---|---|
| Determinism / seed control | Full | No (Math.random) |
| Road generation | Terrain-following DP + Grid/Radial/Organic archetypes | Tensor field + RK4 streamlines |
| Connector organics | FBM drift + turn bias S-curves (Sprint 3) | Streamline curvature |
| Block finding | BFS flood-fill + perimeter facing | Right-turn graph polygon walk |
| Building elevation awareness | Full (Sprint 2) | None |
| Junction classification | highway_junction role + roundabouts (Sprint 3) | None |
| Highway terrain routing | Elevation DP valleys-first (Sprint 3) | No (flat placement) |
| City archetype variety | Grid/Radial/Organic 3× variety (Sprint 3) | None |
| Ring roads | Radial archetype orbital road (Sprint 3) | None |
| Output format | Tile grid (game-ready) | Vector polygons (render-only) |
| RPG metadata | Full | None |
| City profiles | 5 distinct | 1 generic |
| District names | Per-profile per-quadrant (Sprint 1) | N/A |
| World-scale planning | WorldGenerator 48 chunks (Sprint 2) | N/A (single viewport) |
| Performance | <5ms / 96×72 map | Browser-limited |

---

## Implementations This Sprint

### A1: Terrain-Following Highway Routing

**Problem**: `generate_highways()` placed roads on a pure N-S/E-W grid with only mild FBM drift, ignoring the `elevation` field. Roads crossed hilltops as readily as valleys — unrealistic and visually monotonous.

**Algorithm**: 1D dynamic programming per row (N-S) or column (E-W).

For each step along the travel axis:
```
best_cost = min over dc in [-5..+5] of:
    elevation[r][cur_c + dc] * 4.0   // elevation penalty
  + |dc| * 0.25                        // lateral movement cost
  + |cand - target_c| * 0.04          // drift-from-target penalty
  + FBM organic bonus                  // mild organic variation
```

The path follows the minimum-cost cell, accumulating from row 0 to rows-1. Result: roads statistically prefer low-elevation valleys over hilltops, matching real infrastructure placement.

**Stair-step fill**: When consecutive path steps move diagonally, the corner cell is filled to maintain 4-connectivity.

**Smoke verification**: `validate_terrain_routing()` — generates seed 77, 80×60, CoastNone; asserts highway average elevation < non-highway land average elevation.

**Files changed**:
- `mapping_algorithm/cpp/src/map_generator.cpp` — `generate_highways()` fully replaced

---

### A2: City Archetype System + Ring Roads

**Archetype determination**:
```cpp
archetype_ = static_cast<int>(mix_u32(config_.master_seed ^ 0x3A7F9B2CU) % 3U);
// 0=Grid, 1=Radial, 2=Organic
```

**Grid archetype (0)**: Terrain-following N-S + E-W highways as described in A1. No special structure.

**Organic archetype (2)**: Same as Grid, plus one diagonal highway that traverses from col W/4 to col 3W/4 while following local elevation minima (±3 cell scan per row).

**Radial archetype (1)**: 4-6 rays fire outward from `cbd_center_r_/cbd_center_c_` at evenly-spaced angles (with per-ray angle noise from `decision01`). Stair-step fill enforces 4-connectivity. Ring road is added after radial arms.

**Ring road** (`generate_ring_road()`):
- Radius = `round(min(rows, cols) × 0.28)`
- Steps = `round(2π × radius × 2.5)` — oversampled to ensure no gaps
- RoadCategory: Connector (ring supplements, not replaces, highway arms)
- Stair-step gap fill: when |Δr| + |Δc| > 1, fills corner cell
- Skips water cells; only places on valid land

**Files changed**:
- `mapping_algorithm/cpp/include/mapping_algorithm/map_generator.hpp` — `generate_ring_road()`, `cbd_center_r_`, `cbd_center_c_`, `archetype_` members
- `mapping_algorithm/cpp/src/map_generator.cpp` — `generate_highways()` fully replaced, `generate_ring_road()` added

---

### A3: Roundabouts at Highway Junctions

**Algorithm**: After all highway roads are placed, scan every highway cell. If a cell has ≥3 highway-category neighbours (4-connected), it is a junction candidate. Place a connector ring of up to 8 surrounding cells (diagonals included, 3×3 minus center). Budget controlled by `config_.roundabout_count` (default 8).

**Only empty land cells** receive connectors; existing roads and water are skipped.

**Effect**: Roundabouts become natural NPC gathering nodes, complementing the existing `highway_junction` spawn marking.

**Files changed**:
- `mapping_algorithm/cpp/src/map_generator.cpp` — roundabout pass at end of `generate_highways()`

---

### A4: connector_turn_bias

**Problem**: FBM drift on connector streets was smooth and gradual. Real organic street networks show sharper turns — direction reversals where the street hooks left, then right.

**Implementation**: Track `prev_noise_val` across each row (vertical avenues) or column (horizontal connectors). When the FBM noise value changes sign (crosses zero — a direction reversal), amplify the computed drift:

```cpp
if (prev_c2 * curr_c2 < 0.0) {  // sign flip = turn
    amplified_drift = static_cast<int>(std::round(raw_drift * (1.0 + config_.connector_turn_bias * 3.0)));
}
```

At default `connector_turn_bias = 0.08`: amplification factor = 1.24× — adds mild S-curves.
At `connector_turn_bias = 0.5`: factor = 2.5× — produces London-style dog-legs and hooks.

Applied identically to vertical avenues (`prev_noise_val_v`) and horizontal connectors (`prev_noise_val_h`).

**Files changed**:
- `mapping_algorithm/cpp/src/map_generator.cpp` — `generate_connectors()` vertical and horizontal loops

---

### A5: CBD Center Offset + Smoke Tests

**CBD center offset**:
```cpp
const double offset_r = (decision01(seed, 77, 99, SALT_ELEVATION) - 0.5) * 0.10 * rows;
const double offset_c = (decision01(seed, 88, 77, SALT_ELEVATION) - 0.5) * 0.10 * cols;
center_r = std::clamp(center_r + offset_r, rows * 0.20, rows * 0.80);
center_c = std::clamp(center_c + offset_c, cols * 0.20, cols * 0.80);
cbd_center_r_ = center_r;
cbd_center_c_ = center_c;
```

Stored as `cbd_center_r_` / `cbd_center_c_` member variables; consumed by:
- `generate_zones()` (zone ring radii centered here)
- `generate_civic_anchor()` (center score now uses CBD center, not map center)
- `generate_district_names()` (quadrant split along CBD center)
- `generate_highways()` (Radial arm origin; ring road center)
- `generate_ring_road()` (center of circular ring)

**Smoke checks added**:

`validate_terrain_routing()`: Generates seed=77, 80×60, CoastNone. Asserts highway average elevation < non-highway land average elevation. This verifies the DP is actually selecting lower cells.

`validate_map_variation()`: Generates seeds 1-6, 80×60, CoastNone. Asserts max_roads - min_roads ≥ 30. Verifies the archetype system and CBD offset produce measurably different road networks across seeds.

**Files changed**:
- `mapping_algorithm/cpp/src/map_generator.cpp` — `generate_zones()`, `generate_civic_anchor()`, `generate_district_names()`
- `mapping_algorithm/cpp/tests/smoke.cpp` — two new validation functions + main() calls

---

## Deferred (Not Implemented — Intentional)

| Item | Why Deferred |
|---|---|
| Cross-chunk highway stitching | `plan()` done; runtime chunk generation with boundary-aligned highway positions is next sprint |
| Full right-turn polygon block walk | Changes block counts → requires smoke test redesign; high value, 1–2 sprint effort |
| D1: Inland rivers multi-tributary | Single river functional; multi-tributary is future scope |
| D2: Elevation visual tinting | Elevation feeds building selection; visual tinting is a renderer concern |
| C2: std::set→vector for blocks/lots | Memory optimization; no correctness issue |
| C3: MapCell string fields→enum | Memory optimization; no correctness issue |

---

## Verification Matrix

| Check | Result |
|---|---|
| Build (Release, MSVC 19.43 / C++17) | **Clean — 0 errors, 0 warnings on all targets** |
| CTest gate count | 6 tests discovered |
| CTest run | **6/6 passed, 0 failed** |
| Smoke binary direct run | **PASS=78, FAIL=0** |
| Terrain routing: hw_avg < land_avg | Verified seed 77 — highway elevation statistically lower than non-highway land |
| Map variation: max-min roads ≥ 30 | Verified seeds 1-6 — road counts differ measurably across seeds |
| Road ratio guard rail | Within [0.05, 0.50] on all 72 seed/coast/profile configs |
| Road local connectivity | No isolated road cells |
| Lot contiguity | All lot_id groups contiguous |
| Determinism | Same stats on 3 independent runs per config |
| Zone ratios | CBD 5-60%, Residential ≥10% on all configs |
| city_viewer.html | Updated: archetype detection, terrain-following highways, ring road, CBD offset, turn bias, archetype hover panel |
| exports/city_seed_42.json | Regenerated: seed=42 generic_dense 164 buildings 1213 roads 5 landmarks coast=none |

---

## Current Project Structure

```
mapping_algorithm/       C++ generator library + tools
  cpp/src/               map_generator.cpp (v5) + world_generator.cpp
  cpp/include/           map_types.hpp + map_generator.hpp (ring road + archetype members) + world_generator.hpp
  cpp/tests/             smoke.cpp (78 checks)
  cpp/tools/             city_exporter.cpp
mapping_design/          C++ asset validation tools
assets/                  Sprite sheets, atlases, manifests
exports/                 city_seed_42.json (6912 cells, 164 buildings, 1213 roads)
docs/
  MASTER_MIND.md         Pipeline contract
  OPEN_WORLD_SPEC.md     Chunk system spec (8×6 grid, seeding, zones, highways)
  STUDIO_OUTPUT.md       This document (Sprint 3)
test                     QA dashboard HTML — v5 badge, 78/78 status, Sprint 3 features
city_viewer.html         Visual test app — archetype system, terrain highways, ring road, turn bias, CBD offset
generate_city.ps1        Exporter helper script
```

---

## Definition of Done for Sprint 4

1. `ctest -C Release --output-on-failure` stays green (6/6).
2. WorldGenerator chunk loader: `generate_chunk(cx, cy)` calls MapGenerator with boundary-clamped highway entry/exit positions.
3. Cross-chunk highway stitching: road exits one chunk's east edge, enters next chunk's west edge at the same row.
4. Polygon block walk: right-turn walk replaces BFS flood-fill; smoke tests redesigned for new block counts.
5. Multi-tributary river: second river branch probability from existing river course.
6. `test` file updated with Sprint 4 output stats.
