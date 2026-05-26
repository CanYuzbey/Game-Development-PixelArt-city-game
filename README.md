# GameDev Mapping System

Native C++17 procedural isometric city mapping for game worlds.

The repository is now centered on a deployable city pipeline:

- `mapping_algorithm/`: deterministic map generation, lot/building assembly,
  gameplay metadata, smoke tests, and seed JSON export.
- `mapping_design/`: runtime sprite registry validation and C++ asset
  preparation tools for alpha-trimmed, guard-padded atlases.
- `assets/`: prepared source RGBA sheets, runtime atlases, atlas manifests, and
  sprite registry data used by the generator contract.

## Build

```bash
cmake -S . -B build
cmake --build build
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

```bash
build/mapping_algorithm/cpp/mapping_algorithm_smoke
build/mapping_design/cpp/mapping_runtime_asset_validator assets
build/mapping_design/cpp/mapping_asset_validator mapping_design/assets
```

Executable paths vary by CMake generator. Visual Studio generators normally put
executables under a configuration folder such as `Debug` or `Release`.

## Export A City

```bash
build/mapping_algorithm/cpp/mapping_city_exporter \
  --seed 42 \
  --width 96 \
  --height 72 \
  --profile manhattan \
  --coast random \
  --out exports/city_seed_42.json
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
| 2 | Elevation | `MapGenerator::generate_elevation()` |
| 3 | Zones | `MapGenerator::generate_zones()` |
| 4 | Highways | `MapGenerator::generate_highways()` |
| 5 | Connectors | `MapGenerator::generate_connectors()` |
| 6 | Sidewalks | `MapGenerator::generate_sidewalks()` |
| 7 | Blocks | `MapGenerator::generate_blocks()` |
| 8 | Civic anchor | `MapGenerator::generate_civic_anchor()` |
| 9 | Parks | `MapGenerator::generate_parks()` |
| 10 | Lots | `MapGenerator::generate_lots()` |
| 11 | Density | `MapGenerator::compute_density()` |
| 12 | Lot-level building assembly | `MapGenerator::generate_buildings()` |
| 13 | District names | `MapGenerator::generate_district_names()` |
| 14 | Stats | `MapGenerator::compute_stats()` |

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

No runtime scripting language is required by the production source tree.
