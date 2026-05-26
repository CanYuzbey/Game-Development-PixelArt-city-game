# Procedural City Map Generator - Current Quality Report

## Current Verdict

The project is organized as a C++17 source tree with native map generation,
runtime asset validation, seed export, and Windows-native runtime atlas
preparation source.

## Native Quality Gates

### Mapping Gate

Executable: `mapping_algorithm_smoke`

Coverage:

- 12 seeds.
- 6 coast modes, including deterministic `random` resolution.
- deterministic repeat generation on fresh and reused generators.
- structural checks for land, roads, blocks, lots, parks, spawns, landmarks,
  buildings, and blueprint records.
- design blueprint checks for profile identity, resolved coast side, roads,
  blocks, lots, buildings, sprite assignments, and normalized asset slots.
- invalid-config rejection.

### Runtime Asset Gate

Executable: `mapping_runtime_asset_validator`

Coverage:

- sprite registry schema check,
- total sprite count match,
- no estimated sprites,
- every sprite exported,
- prepared trim metadata present,
- atlas PNG headers readable,
- atlas rects inside atlas dimensions,
- required slot coverage for terrain, streets, buildings, roofs, shadows,
  facade kits, and landmarks.

### Asset Preparation Tool

Executable: `mapping_runtime_asset_preparer`

Coverage:

- reads `assets/source_rgba`,
- crops by registry `pixel_rect`,
- alpha-trims visible art,
- adds transparent guard padding,
- procedurally creates orthogonal road and sidewalk bitmask tiles,
- shelf-packs runtime atlases,
- writes `runtime_registry_cpp.json`.

## City Planning Criteria

The generator optimizes toward:

- connected and believable road networks,
- profile-specific road density and diagonal behavior,
- parks distributed through useful city blocks,
- lot-level building metadata,
- combined sprite stacks for full building assembly,
- distinct civic and landmark placement,
- stable district identity,
- design records that let sprites and future game logic attach without
  guessing.

## Remaining Work

1. Install a C++ toolchain in this workspace and run the native gates.
2. Add engine-specific rendering and draw-order integration.
3. Add performance benchmarks for large maps.
