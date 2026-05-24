# Project Master Mind

## Current Mission

Build and preserve a deterministic procedural city generator for an open-world
RPG map. The expected output is a seed-driven city grid with water/coastline,
elevation, zones, civic anchor, highways, connector roads, sidewalks, interior
blocks, parks, lots, setbacks, building metadata, encounter/spawn data,
landmarks, density scores, and district names.

## Pipeline

The production pipeline is:

1. Coastline
2. Elevation
3. Zones
4. Civic anchor
5. Highways
6. Connectors
7. Sidewalks
8. Blocks
9. Parks
10. Lots
11. Density post-pass
12. Buildings and gameplay metadata
13. District naming

`MapGenerator` is the single orchestration owner. Phase modules should stay
focused on one layer of city structure and communicate through `MapCell` fields.

## Acceptance Contract

Primary gate: `tests/full_suite.py`.

Required result:

- 60 configs pass: 12 seeds x 5 coast modes at 80x60.
- Road density stays between 15% and 35% of land cells.
- Every map has at least one park.
- Every map has at least three landmark types.
- `app.cell_color()` never crashes for generated cells.
- No land cell is missing `tile_role`.
- No valid lot cell is missing `building_type`.
- Setbacks cannot receive building roles.
- Parks must keep park roles.
- No orphan road cells.
- Land cells receive elevation.
- District names are generated.
- Same seed and same config produce the same gameplay map fingerprint.

## Feedback Sub-Agents

- Architecture Feedback: owns pipeline shape, module boundaries, public API,
  config drift, and phase-order coupling risks.
- Customer Mapping Feedback: owns expected result, acceptance criteria, docs,
  visual output expectations, and gaps between customer promise and tests.
- Optimization Feedback: owns pathing correctness, hotspot scans, algorithmic
  complexity, and low-risk speed/correctness improvements.
- Quality Gate Feedback: owns `tests/full_suite.py`, targeted diagnostics, and
  deterministic regression checks.

## Current Condition

The generator is structurally mature and the 60-map quality gate is green.
The most important recent fixes were:

- `app.cell_color()` is importable without Pygame so headless quality checks run.
- Highway and diagonal street backtracking now removes the popped dead-end from
  `visited`, instead of accidentally unmarking the retained parent cell.
- Landmark boundary lot selection now checks every cell in a lot when searching
  near a zone boundary.
- Save-load fallback defaults now match `MapConfig` defaults.
- Elevation is a public phase constant.
- The full suite now includes representative deterministic fingerprint checks.

## Optimization Priorities

1. Keep the generator deterministic before every visual or structural change.
2. Prefer O(N) grid scans over nested lot x grid passes.
3. Keep road repair after any feature that can add road cells.
4. Treat `MapConfig` defaults as the single source of truth for docs and
   serialization fallback behavior.
5. Expand visual regression later with screenshot or pixel-diff tooling.

## Do Not Break

- `MapGenerator.generate()` must remain yield-based for game-loop loading.
- Core `map_builder` must stay free of mandatory Pygame dependency.
- Same seed and same config must produce identical map data except elapsed time.
- The visual app may depend on Pygame, but tests may import color logic headlessly.
