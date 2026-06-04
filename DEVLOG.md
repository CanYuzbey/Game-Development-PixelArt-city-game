# Development Log

## Unity C# Runtime Port

The project now has a Unity-ready C# runtime under
`unity/Assets/Scripts/Mapping`.

### Current State

- `MapTypes.cs` owns Unity-serializable config, cell, stats, blueprint, building,
  and sprite assignment contracts.
- `MappingStrings.cs` owns stable profile and serialized string conversions.
- `MapGenerationPhase.cs` exposes the production phase order:
  land/sea, highways, roads, bridges/turns, buildings.
- `MapGenerator.cs` ports the deterministic procedural city generator to C#.
- `WorldGenerator.cs` owns open-world chunk planning and canonical chunk seed
  derivation for Unity streaming.
- `CityMapJsonExporter.cs` exports `deployable_city_map.v2` JSON without native
  tooling.
- `UnityCityChunkBehaviour.cs` provides an inspector-friendly generation bridge.
- `unity/Smoke/MappingAlgorithmSmoke.cs` verifies the C# runtime outside Unity.

### C# Quality Gate

- Compiled with Visual Studio Roslyn `csc.exe` using `/langversion:7.3`.
- Smoke result: `mapping_algorithm_csharp_smoke PASS=78 FAIL=0`.

### Management Direction

Unity gameplay should integrate through the C# runtime. Native C++ remains
available as a reference implementation and for asset preparation/validation
until Unity-side rendering and import workflows fully replace those duties.

## Previous Native C++ Migration And City Assembly

Before the Unity C# runtime port, the project had been migrated to a native
C++17 source tree.

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
2. inland river and bridge crossings,
3. elevation,
4. zones,
5. highways,
6. connectors,
7. sidewalks,
8. blocks,
9. civic anchor,
10. parks,
11. lots,
12. density,
13. lot-level building assembly and gameplay metadata,
14. district names,
15. stats.

### Next Engineering Targets

- Compile and run the C++ gates with MSVC, Clang, and GCC.
- Add a renderer-facing C++ sample once the game engine target is selected.
- Add engine-specific draw ordering once the renderer target is selected.
