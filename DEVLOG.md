# Map Builder — Development Log

---

## Sprint 5 — Missing Parts (May 10, 2026)

**Theme**: Seven features identified in the Sprint 4 Perfection Report implemented, 60-config test suite created, and three latent bugs fixed.

### Features Implemented

**Feature 1 — Full 60-Configuration Test Suite** (`tests/full_suite.py`, `tests/diag.py`)
- Created `tests/diag.py`: detailed diagnostic script printing per-config metrics and FAIL reasons.
- Created `tests/full_suite.py`: definitive quality gate verifying render safety, road density (15–35%), landmark count (≥3), park count (≥1), elevation coverage, district name generation, and footprint style assignment across all 60 configs.
- Exit code 0 = GREEN build; exit code 1 = RED.

**Feature 2 — Smooth Highway Curves** (`map_builder/phases/highway.py`)
- Replaced per-step random drift with a momentum-based organic tracer.
- `momentum_dr` / `momentum_dc` accumulate with `_ALPHA=0.18` low-pass filter, producing gentle S-curves that reverse over ~10 cells instead of staircase zigzags.

**Feature 3 — Procedural District Naming** (`map_builder/map_generator.py`, `app.py`)
- Added `_generate_district_names()` method that assigns human-readable names to zones based on position (North/South/East/West prefix), zone type (CBD → "Financial District"; Midtown → "Arts District"; Residential → "Heights"/"Gardens"/"Park"), coastal proximity (Waterfront/Harbour prefix), and nearest civic landmark.
- Names stored in `gen.stats['districts']` and on `cell.district_name`.
- District names shown in the HUD stats bar in `app.py`.

**Feature 4 — Building Footprint Variation** (`map_builder/phases/buildings.py`, `map_builder/map_state.py`, `app.py`)
- Added `footprint_style: str = ''` field to `MapCell`.
- Large lots (≥16 cells) in CBD/Midtown: 40% courtyard, 30% L-shape, 30% solid.
- `_apply_footprint_style()` marks interior cells with `tile_role=ROLE_WALKABLE_PLAZA` and clears `building_type` for open-air courtyard/L-shape cells.
- `app.py` renders plaza interiors as `C_PLAZA` (warm stone colour).

**Feature 5 — Waterfront CBD Density Boost** (`map_builder/phases/buildings.py`)
- "Prime waterfront CBD" lots (CBD zone + adjacent to water) get `density_score += 0.25` (clamped to 1.0).
- Results in darker, higher-glass-tower rendering tones for waterfront financial district blocks.

**Feature 6 — Dead Code Removal + MapCell Audit** (`map_builder/map_state.py`, `map_builder/phases/connector.py`)
- Removed `variation: dict` field from `MapCell` — it was written but never read by `app.py` or any phase.
- Removed all `self.variation[LAYER_X] = …` assignments from `set_road`, `set_sidewalk`, `set_ground`, `set_decor`.
- Removed stray `cell.variation[LAYER_ROAD] = rng.randrange(…)` line from `connector.py` (would have crashed post-removal).
- `tile_registry.py` retained — documented as sprite-engine integration layer for future game renderer.

**Feature 7 — Elevation Layer** (`map_builder/phases/elevation.py`, `map_builder/map_generator.py`, `map_builder/map_state.py`, `app.py`)
- New `elevation.py` phase inserted between Coastline and Zones.
- FBM noise (3 octaves, persistence=0.5) computes smooth 0–1 elevation on all land cells; water cells always 0.0.
- Added `elevation: float = 0.0` to `MapCell`.
- `app.py` adjusts cell brightness: +8 brightness for high elevation, −6 for low, giving subtle topographic depth.

### Bugs Fixed

**BUG 1 — BFS Connectivity Keeps Wrong Component** (`map_builder/phases/connector.py`)
- Old "Pass 3.5" started connectivity-repair BFS from `all_road_cells[0]`.
- On coastal maps, the first road cell (row-major scan) could be a tiny isolated peninsula fragment, causing the entire main road network to be classified as "isolated" and removed.
- Fix: multi-source BFS that identifies all connected components; only the *largest* component is kept.

**BUG 2 — Landmark Injection Overrides Setback/Park Cells** (`map_builder/phases/buildings.py`)
- Station/Hospital/Police/School landmark injection was assigning `tile_role=ROLE_BUILDING_*` to `is_setback=True` and `is_park=True` cells.
- Fix: added guard `if getattr(grid[r][c], 'is_setback', False) or grid[r][c].is_park: continue` in all `_inject_landmarks` sub-functions.
- Civic anchor guard: `if not anchor_cell.is_park: anchor_cell.tile_role = ROLE_BUILDING_CIVIC`.

**BUG 3 — seed=7 coast=east road%=36.6 (above 35% limit)** (`map_builder/phases/connector.py`)
- Gap-fill pass was unaware of perimeter streets, adding redundant secondary streets adjacent to already-placed perimeter roads.
- Additionally, gap-fill probability of 0.65 let many medium-sized gaps (>1 block) all fill, compounding the issue.
- Fix: pass perimeter street lists into gap-fill input so it accounts for perimeter coverage; reduce gap-fill probability from 0.65 → 0.45 for both NS avenues and EW streets. Result: seed=7 east road%=36.6 → 32.9%.

### Test Results
- **`python tests/diag.py`**: 60/60 PASS, 0 render errors.
- **`python tests/full_suite.py`**: 60/60 PASS — build GREEN.
- Road density: all 60 configs within 22.3%–34.0%.
- All 60 configs: ≥1 park, ≥3 landmarks, 0 render crashes, 0 orphan roads, elevation set on land cells, districts generated.

### Files Changed
| File | Change |
|---|---|
| `map_builder/map_state.py` | Added `elevation`, `footprint_style`, `district_name` fields; removed `variation` dict |
| `map_builder/map_generator.py` | Added elevation phase call; added `_generate_district_names()` |
| `map_builder/phases/elevation.py` | **NEW** — FBM elevation layer phase |
| `map_builder/phases/highway.py` | Momentum-based smooth curve tracer |
| `map_builder/phases/buildings.py` | Footprint variation, waterfront boost, landmark injection guard |
| `map_builder/phases/connector.py` | Multi-source BFS repair, perimeter-aware gap-fill, probability 0.65→0.45 |
| `app.py` | Elevation brightness, plaza rendering, district HUD, phase colour |
| `tests/diag.py` | **NEW** — 60-config detailed diagnostic |
| `tests/full_suite.py` | **NEW** — definitive 60-config quality gate |
| `docs/PERFECTION_REPORT.md` | Sprint 5 section added |

---

## Sprint 4 — Final Sprint (May 9, 2026)

**Theme**: Realism polish — park scaling, waterfront buildings, residential setbacks, soft zone transitions, alley/cul-de-sac distinction.

### Features Implemented

**A — Dynamic Park Count Scaling** (`parks.py`, `constants.py`)
- Replaced hardcoded `PARK_MAX_PER_ZONE=2` with a runtime formula: `dynamic_max = max(1, min(4, land_cells // 500))`.
- Parks now scale naturally with map size: 80×60 map → 3 parks/zone; 160×120 → up to 4 parks/zone.
- Matches WHO 9 m²/person standard across realistic map sizes.

**B — Waterfront Building Types** (`buildings.py`, `constants.py`)
- Added `WATERFRONT_BLDG_WEIGHTS` (restaurant 35%, market 25%, apartment 20%, ferry terminal 10%, empty 10%).
- Lots with any cell adjacent to water now draw from the waterfront weight table instead of their zone table.
- Produces realistic coastal zones: restaurants and markets dominate, offices are absent.

**C — Residential Setbacks** (`lots.py`, `map_state.py`, `app.py`)
- Added `is_setback: bool` field to `MapCell`.
- After lot subdivision, residential lots with ≥ 9 cells have their 1-cell perimeter marked `is_setback=True` with `tile_role=ROLE_WALKABLE_SIDEWALK`.
- Rendered as warm light-green `(188, 195, 160)` — visually distinct from sidewalk and buildings.
- Buildings phase skips setback cells so no building footprint is assigned to front-yard cells.
- Matches real residential setback codes: 3–6 m front yard required.

**D — Soft Zone Transitions** (`zones.py`)
- After initial Chebyshev zone assignment, a softening pass flips boundary cells:
  - CBD→Midtown boundary: 40% flip probability (seeded `master_seed ^ 0xBEEF`).
  - Midtown→Residential boundary: 35% flip probability.
- Produces organic 1–2 cell ragged transition strips instead of hard geometric edges.
- Civic anchor cell is protected from zone flipping.

**E — Alley vs Cul-de-sac Distinction** (`buildings.py`)
- Dead-end connector roads now have their length measured via BFS walk.
- Length ≤ 3 cells → `ROLE_WALKABLE_ALLEY` (service lane, high danger).
- Length > 3 cells → `ROLE_WALKABLE_ROAD` (cul-de-sac, normal street safety).

### Test Results
- 30 configurations (10 seeds × 3 coast modes, 80×60 map): **0 crashes, 0 errors**.
- All `cell_color()` calls succeed across every configuration.
- Park range: 0–7 per map; waterfront detected in all coastal configs; setbacks detected in residential-heavy configs.

### Files Changed
| File | Change |
|---|---|
| `map_builder/constants.py` | Added `WATERFRONT_BLDG_WEIGHTS`; annotated `PARK_MAX_PER_ZONE` |
| `map_builder/map_state.py` | Added `is_setback` field to `MapCell` |
| `map_builder/phases/parks.py` | Dynamic park cap replacing hardcoded constant |
| `map_builder/phases/buildings.py` | Waterfront detection, alley length check, setback guard |
| `map_builder/phases/lots.py` | Residential setback pass after lot subdivision |
| `map_builder/phases/zones.py` | Noise-softened zone boundary transition pass |
| `app.py` | Setback colour `(188, 195, 160)` in `cell_color()` |

### Deletions
- `test_rpg_layer.py` — standalone Sprint 2 test script, superseded by new test harness.
- `map_builder/sheet_analyzer.py` — PIL-based sprite sheet extractor tool, not used at runtime.
- All `reports/team*.md` files — findings fully implemented; consolidated here.

---

## Sprint 3 — Visual Realism Overhaul (May 9, 2026, earlier)

**Theme**: OSM-calibrated colour palette, per-lot building variation, building edge rendering.

### Features Implemented
- **OSM/Google Maps calibrated colour palette** (`app.py`): Water, highways, connectors, sidewalks, parks, all buildings recoloured to match real OSM tile colours. Verified against aerial references.
- **Per-lot deterministic colour variation** (`app.py`): Fast 3-tap LCG gives each lot a unique but consistent colour offset. CBD buildings darken under high density; residential buildings warm at low density.
- **Building edge rendering** (`app.py`): At cell_sz ≥ 3, 1px dark edges drawn at lot boundaries. At 5 ≤ cell_sz < 16, inset cell borders add facade texture.
- **BFS density field** (`map_generator.py`): O(N²) loop replaced with O(N) multi-source BFS from highway cells. 200–1000× faster on large maps.
- **Landmark minimum separation** (`buildings.py`): Town Hall, Station, Hospital, Police Station guaranteed ≥ 6 Chebyshev cells apart.

### Bugs Fixed
- `ROLE_WALKABLE_PARK` missing from `app.py` import → crash on park cells.
- Cul-de-sac bitmask not updated after placement → wrong tile glyph.
- `zone_id` defaulted to CBD (0) instead of -1 sentinel → semantic errors in buildings phase.
- Park `tile_role` not set in `parks.py` → inconsistency with buildings phase.

---

## Sprint 2 — RPG Game Data Layer (May 9, 2026, earlier)

**Theme**: Full game-ready tile classification, encounter system, landmarks, spawn points.

### Features Implemented
- **`tile_role` assignment** (`buildings.py`): Every cell gets a `ROLE_*` constant for traversability.
- **`building_type` assignment** (`buildings.py`): Per-zone weighted random building types (office, shop, house, etc.) assigned to all lot cells.
- **Encounter probability** (`buildings.py`): Research-grade formula `(base + density_bonus) * zone_mult + zone_offset − civic_penalty` for each walkable cell.
- **Landmark injection** (`buildings.py`): Town Hall at civic anchor, Station near CBD highway junction, Hospital in Midtown, Police Station at CBD boundary.
- **Spawn points** (`buildings.py`): 1 spawn per 10 road cells in CBD/Midtown, 1 per 25 in Residential; all park cells are spawn points.
- **Civic anchor** (`civic.py`): Single ROLE_BUILDING_CIVIC cell placed at CBD centre, acts as encounter safety zone.

---

## Sprint 1 — Procedural Foundation (May 9, 2026, initial)

**Theme**: Full procedural city generation pipeline from scratch.

### Pipeline Phases Implemented (in order)
1. **Coastline** (`coastline.py`): Perlin FBM + directional gradient → water/land assignment with smoothing passes.
2. **Zones** (`zones.py`): Chebyshev distance from shifted city centre → CBD / Midtown / Residential zones.
3. **Civic Anchor** (`civic.py`): Selects CBD land cell furthest from water as the town centre.
4. **Highways** (`highway.py`): N–S and E–W arterial roads with organic deviation and roundabouts.
5. **Connectors** (`connector.py`): Dense grid of local streets with diagonal Broadway-style avenues.
6. **Sidewalks** (`sidewalk.py`): 1-cell sidewalk bands on connector-adjacent land cells with correct bitmask tiles.
7. **Blocks** (`blocks.py`): Flood-fill interior block detection; exterior = void.
8. **Parks** (`parks.py`): Priority-scored block selection with separation constraint.
9. **Lots** (`lots.py`): Recursive alternating-axis binary split with ±20% noise offset.
10. **Buildings** (`buildings.py`): RPG data layer assignment (see Sprint 2).

### Architecture Decisions
- Pure Python, no external dependencies except Pygame for the visual demo.
- Single `master_seed` controls all phases deterministically via per-phase XOR salts.
- `MapCell` dataclass holds all per-cell state; `MapGrid` is a flat 2-D array of `MapCell`.
- Generator-based pipeline yields `GeneratorProgress` at each step for non-blocking game-loop integration.
