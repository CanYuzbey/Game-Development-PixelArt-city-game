# Development Log

## C++-Only Migration

The project has been migrated to a native C++17 source tree.

### Current State

- `mapping_algorithm/cpp` owns procedural city generation.
- `mapping_design/cpp` owns design-side validation tooling.
- The repository root owns the combined CMake build.
- The retained assets and design reports live under `mapping_design/`.
- The previous reference/demo/test source files have been removed from the
  tracked project.

### Native Quality Gates

- `mapping_algorithm_smoke`
  - runs 12 seeds across 5 coast modes,
  - checks deterministic repeat generation,
  - verifies land, roads, blocks, lots, parks, spawns, landmarks, and blueprint
    records.
- `mapping_asset_validator`
  - checks the asset manifest schema,
  - confirms every listed raw asset exists,
  - verifies PNG signatures for listed sheets.

### Current Architecture

The generation pipeline is implemented inside `mapping_algorithm::MapGenerator`:

1. coastline,
2. elevation,
3. zones,
4. civic anchor,
5. highways,
6. connectors,
7. sidewalks,
8. blocks,
9. parks,
10. lots,
11. density,
12. buildings and gameplay metadata,
13. district names,
14. stats.

### Next Engineering Targets

- Compile and run the C++ gates with MSVC, Clang, and GCC.
- Add native serialization for `MapConfig`, `MapStats`, and `DesignBlueprint`.
- Add a renderer-facing C++ sample once the game engine target is selected.
- Replace raw asset candidates with sliced alpha-ready sprite records.
