# Development Log

## C++-Only Migration And City Assembly

The project has been migrated to a native C++17 source tree.

### Current State

- `mapping_algorithm/cpp` owns procedural city generation.
- `mapping_design/cpp` owns design-side validation tooling.
- `assets/source_rgba`, `assets/runtime`, and `assets/manifests` hold the
  current runtime sprite-sheet pipeline outputs.
- The repository root owns the combined CMake build.
- The retained assets and design reports live under `mapping_design/`.
- The previous reference/demo/test source files have been removed from the
  tracked project.

### Native Quality Gates

- `mapping_algorithm_smoke`
  - runs 12 seeds across 6 coast modes,
  - checks deterministic repeat generation on fresh and reused generators,
  - verifies land, roads, blocks, lots, parks, spawns, landmarks, buildings,
    and blueprint records.
- `mapping_asset_validator`
  - checks the asset manifest schema,
  - confirms every listed raw asset exists,
  - verifies PNG signatures for listed sheets.
- `mapping_runtime_asset_validator`
  - validates the runtime sprite registry,
  - validates C++-prepared runtime atlases by default,
  - rejects estimated or non-exported legacy registry sprites,
  - confirms prepared trim metadata,
  - validates atlas PNG headers and atlas rect bounds,
  - checks required runtime slots.
- `mapping_runtime_asset_preparer`
  - regenerated `assets/runtime_cpp`,
  - prepared 274 sprites across 11 atlases,
  - added transparent guard padding,
  - generated orthogonal road and sidewalk bitmask tiles in C++.
- `mapping_city_exporter`
  - writes a deployable JSON city map for one seed/config.

### Current Architecture

The generation pipeline is implemented inside `mapping_algorithm::MapGenerator`:

1. coastline,
2. elevation,
3. zones,
4. highways,
5. connectors,
6. sidewalks,
7. blocks,
8. civic anchor,
9. parks,
10. lots,
11. density,
12. lot-level building assembly and gameplay metadata,
13. district names,
14. stats.

### Next Engineering Targets

- Compile and run the C++ gates with MSVC, Clang, and GCC.
- Add a renderer-facing C++ sample once the game engine target is selected.
- Add engine-specific draw ordering once the renderer target is selected.
