# Unity C# Port

## Head Developer Summary

The project motive is a deterministic, seed-driven isometric city and open-world
mapping system for a full Unity game. The generator produces more than terrain:
it creates roads, coast and river cells, elevation, zones, blocks, parks, lots,
building assemblies, landmarks, spawn points, encounter weights, district names,
sprite assignments, and deployable JSON data.

The C++ implementation remains useful as a reference and asset-pipeline owner,
but Unity gameplay needs the runtime logic in C#. The Unity port now lives in:

```text
unity/Assets/Scripts/Mapping/
```

## C# Runtime Scope

The port includes:

- `MapTypes.cs`: Unity-serializable config, cells, stats, blueprint records, and
  sprite assignment records.
- `MappingStrings.cs`: stable string conversion and city-profile validation.
- `MapGenerationPhase.cs`: explicit generation pipeline order.
- `MapGenerator.cs`: translated procedural city generation phases.
- `WorldGenerator.cs`: open-world chunk planning, canonical chunk seed formula,
  world-zone profile assignment, coast assignment, and highway-grid metadata.
- `CityMapJsonExporter.cs`: pure C# `deployable_city_map.v2` JSON export.
- `UnityCityChunkBehaviour.cs`: optional MonoBehaviour bridge for inspector-driven
  chunk generation.
- `GameDev.Mapping.asmdef`: Unity assembly definition.

The C# namespace is:

```csharp
GameDev.Mapping
```

## Unity Usage

Copy or keep the `unity/Assets/Scripts/Mapping` folder inside a Unity project.
Then generate a chunk from gameplay code:

```csharp
using GameDev.Mapping;

var config = new MapConfig
{
    width = 96,
    height = 72,
    masterSeed = 42,
    cityProfile = "manhattan",
    coastSide = CoastSide.Random
};

var generator = new MapGenerator(config);
generator.Generate();

MapGrid grid = generator.Grid;
DesignBlueprint blueprint = generator.ToDesignBlueprint();
string json = CityMapJsonExporter.ToJson(generator, blueprint);
```

For inspector testing, attach `UnityCityChunkBehaviour` to a GameObject and use
the context menu item `Generate City Chunk`.

## Organizational Boundary

Use the C# runtime for Unity gameplay, rendering integration, streaming, save
cache generation, and editor tooling.

Keep C++ tools only where they still provide value:

- atlas preparation,
- runtime asset validation,
- legacy parity checks,
- reference implementation comparison.

Future cleanup can remove or archive native generation once the Unity renderer
and asset importer prove the C# output end to end.

## Verification

The standalone C# smoke harness is:

```text
unity/Smoke/MappingAlgorithmSmoke.cs
```

It verifies deterministic generation, reused-generator determinism, gameplay
layers, blueprint shape, asset slot contracts, world planning, large chunk
generation, phase order, bridge/turn/intersection annotations, cross-chunk
highway boundaries, JSON export, and invalid-config rejection.

Last local run:

```text
mapping_algorithm_csharp_smoke PASS=78 FAIL=0
```

The port was compiled with Roslyn using C# 7.3 compatibility.
