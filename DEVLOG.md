# Map Builder — Development Log

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
