# GameDev Mapping System

Unity-ready C# procedural isometric city mapping for game worlds, with the
native C++ pipeline retained as reference and asset tooling.

The repository is now centered on a deployable city pipeline:

- `unity/Assets/Scripts/Mapping/`: Unity C# runtime port for deterministic map
  generation, world chunk planning, gameplay metadata, blueprint records, and
  deployable JSON export.
- `mapping_algorithm/`: native reference implementation, smoke tests, and seed
  JSON export.
- `mapping_design/`: runtime sprite registry validation and C++ asset
  preparation tools for alpha-trimmed, guard-padded atlases.
- `assets/`: prepared source RGBA sheets, runtime atlases, atlas manifests, and
  sprite registry data used by the generator contract.

## Build

```bash
cmake -S . -B build
cmake --build build --config Release
```

The top-level build creates:

- `mapping_algorithm_demo`: prints a generated city summary.
- `mapping_city_exporter`: exports a fully inspectable deployable city JSON.
- `mapping_algorithm_smoke`: runs deterministic algorithm and blueprint gates.
- `mapping_asset_validator`: validates the design raw-sheet manifest.
- `mapping_runtime_asset_validator`: validates `assets/manifests/runtime_registry_cpp.json`
  against C++-prepared runtime atlas PNGs.
- `mapping_runtime_asset_preparer`: Windows-native WIC tool that crops,
  alpha-trims, adds transparent guard padding, procedurally generates clean
  orthogonal road/sidewalk bitmask tiles, packs atlases, and writes a runtime
  manifest.

## Run Checks

Preferred release gate after building:

```bash
cd build
ctest -C Release --output-on-failure
```

The registered CTest suite runs the algorithm smoke gate, the exporter
bad-input rejection checks, the raw asset manifest validator, and the runtime
asset registry validator.

For Visual Studio Release builds, the direct gate executables are normally:

```bash
build/mapping_algorithm/cpp/Release/mapping_algorithm_smoke
build/mapping_design/cpp/Release/mapping_runtime_asset_validator assets
build/mapping_design/cpp/Release/mapping_asset_validator mapping_design/assets
```

Executable paths vary by CMake generator. Visual Studio generators normally put
executables under a configuration folder such as `Debug` or `Release`.

## Export A City

Visual Studio Release example:

```powershell
.\build\mapping_algorithm\cpp\Release\mapping_city_exporter.exe `
  --seed 42 `
  --width 96 `
  --height 72 `
  --profile manhattan `
  --coast random `
  --out exports\city_seed_42.json
```

The helper script wraps the same exporter and can optionally open the HTML
concept viewer with matching generation parameters:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\generate_city.ps1 `
  -Seed 42 `
  -Profile manhattan `
  -Coast random `
  -OpenViewer
```

The exported JSON contains stats, resolved coast side, profile tags, roads,
blocks, lots, landmarks, assembled buildings, sprite assignments, and every map
cell with role/zone/lot/building metadata.

## C++ Library Usage

```cpp
#include "mapping_algorithm/map_generator.hpp"

using namespace mapping_algorithm;

MapConfig config;
config.width = 80;
config.height = 60;
config.master_seed = 42;
config.coast_side = CoastSide::Random;
config.city_profile = "manhattan";

MapGenerator generator(config);
generator.generate();

const MapGrid& grid = generator.grid();
DesignBlueprint blueprint = generator.to_design_blueprint();
```

## Generation Pipeline

| # | Phase | Native owner |
|---|-------|--------------|
| 1 | Coastline | `MapGenerator::generate_coastline()` |
| 2 | Inland river and bridge crossings | `MapGenerator::generate_river()` |
| 3 | Elevation | `MapGenerator::generate_elevation()` |
| 4 | Zones | `MapGenerator::generate_zones()` |
| 5 | Highways | `MapGenerator::generate_highways()` |
| 6 | Connectors | `MapGenerator::generate_connectors()` |
| 7 | Sidewalks | `MapGenerator::generate_sidewalks()` |
| 8 | Blocks | `MapGenerator::generate_blocks()` |
| 9 | Civic anchor | `MapGenerator::generate_civic_anchor()` |
| 10 | Parks | `MapGenerator::generate_parks()` |
| 11 | Lots | `MapGenerator::generate_lots()` |
| 12 | Density | `MapGenerator::compute_density()` |
| 13 | Lot-level building assembly | `MapGenerator::generate_buildings()` |
| 14 | District names | `MapGenerator::generate_district_names()` |
| 15 | Stats | `MapGenerator::compute_stats()` |

## Design Blueprint Contract

`MapGenerator::to_design_blueprint()` returns a native C++ record containing:

- seed, algorithm version, resolved coast side, and city profile,
- road records with category, zone, bitmask, and normalized `street/road` slot,
- block and lot records,
- landmark records,
- lot-level `BuildingAssemblyRecord` entries,
- renderer-ready `SpriteAssignmentRecord` entries,
- required runtime asset slots.

## Dependencies

- C++17 compiler.
- CMake 3.16 or newer.
- Windows Imaging Component for `mapping_runtime_asset_preparer` on Windows.

## Unity C# Runtime

The Unity integration path is documented in `docs/UNITY_CSHARP_PORT.md`.

The deployable mock-test app is documented in `docs/MOCK_APP.md` and lives at
`deployable_mock_app/MapGeneratorMockApp.html`.

Minimal C# usage:

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

DesignBlueprint blueprint = generator.ToDesignBlueprint();
string json = CityMapJsonExporter.ToJson(generator, blueprint);
```

Standalone C# smoke verification:

```powershell
& 'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\Roslyn\csc.exe' `
  /nologo /langversion:7.3 `
  /out:build\mapping_algorithm_csharp_smoke.exe `
  unity\Assets\Scripts\Mapping\MapTypes.cs `
  unity\Assets\Scripts\Mapping\MappingStrings.cs `
  unity\Assets\Scripts\Mapping\MapGenerationPhase.cs `
  unity\Assets\Scripts\Mapping\MapGenerator.cs `
  unity\Assets\Scripts\Mapping\WorldGenerator.cs `
  unity\Assets\Scripts\Mapping\CityMapJsonExporter.cs `
  unity\Assets\Scripts\Mapping\UnityCityChunkBehaviour.cs `
  unity\Smoke\MappingAlgorithmSmoke.cs

.\build\mapping_algorithm_csharp_smoke.exe
```

The C# port does not require a native runtime dependency inside Unity.
