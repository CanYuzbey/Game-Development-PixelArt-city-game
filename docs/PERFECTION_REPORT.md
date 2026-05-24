# Procedural City Map Generator - Current Quality Report

## Current Verdict

The project is now organized as a C++17 source tree with native mapping and
design-validation code.

## Native Quality Gates

### Mapping Gate

Executable: `mapping_algorithm_smoke`

Coverage:

- 12 seeds.
- 5 coast modes.
- deterministic repeat generation per config.
- structural checks for land, roads, blocks, lots, parks, spawns, and
  landmarks.
- design blueprint checks for profile identity, roads, blocks, lots, and asset
  requirements.

### Asset Gate

Executable: `mapping_asset_validator`

Coverage:

- manifest schema check,
- raw sheet file presence,
- PNG signature check.

## City Planning Criteria

The generator should continue to optimize toward:

- connected and believable road networks,
- sensible road density relative to land area,
- compact parks distributed through useful city areas,
- lots with meaningful building metadata,
- distinct civic and landmark placement,
- stable district identity,
- design records that let sprites and future game logic attach without guessing.

## Remaining Work

1. Compile the native gates on MSVC, Clang, and GCC.
2. Add native serialization for design blueprints.
3. Add a renderer-facing C++ sample once the game engine target is selected.
4. Replace raw sprite-sheet candidates with sliced, alpha-ready runtime sprite
   records.
5. Add performance benchmarks for large maps.
