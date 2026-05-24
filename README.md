# GameDev Mapping System

Seed-based procedural city mapping for game worlds, implemented as a C++17
codebase.

The project is split into two production work areas:

- `mapping_algorithm/`: native map generation, gameplay metadata, and design
  blueprint export.
- `mapping_design/`: city design assets, asset audit notes, and native asset
  validation.

## Build

```bash
cmake -S . -B build
cmake --build build
```

The top-level build creates:

- `mapping_algorithm_demo`: prints a generated city summary.
- `mapping_algorithm_smoke`: runs the deterministic 60-configuration algorithm
  and design-export quality gate.
- `mapping_asset_validator`: validates the design asset manifest and raw PNG
  sheet presence.

## Run Checks

```bash
build/mapping_algorithm/cpp/mapping_algorithm_smoke
build/mapping_design/cpp/mapping_asset_validator mapping_design/assets
```

Executable paths can vary by generator and platform. On Visual Studio
generators, the executable may live under a configuration folder such as
`Debug` or `Release`.

## C++ Library Usage

```cpp
#include "mapping_algorithm/map_generator.hpp"

using namespace mapping_algorithm;

MapConfig config;
config.width = 80;
config.height = 60;
config.master_seed = 42;
config.coast_side = CoastSide::West;
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
| 4 | Civic anchor | `MapGenerator::generate_civic_anchor()` |
| 5 | Highways | `MapGenerator::generate_highways()` |
| 6 | Connectors | `MapGenerator::generate_connectors()` |
| 7 | Sidewalks | `MapGenerator::generate_sidewalks()` |
| 8 | Blocks | `MapGenerator::generate_blocks()` |
| 9 | Parks | `MapGenerator::generate_parks()` |
| 10 | Lots | `MapGenerator::generate_lots()` |
| 11 | Density | `MapGenerator::compute_density()` |
| 12 | Buildings/game data | `MapGenerator::generate_buildings()` |
| 13 | District names | `MapGenerator::generate_district_names()` |
| 14 | Stats | `MapGenerator::compute_stats()` |

## Repository Layout

```text
GameDev/
├── CMakeLists.txt
├── DEVLOG.md
├── README.md
├── mapping_algorithm/
│   ├── README.md
│   └── cpp/
│       ├── CMakeLists.txt
│       ├── examples/
│       ├── include/mapping_algorithm/
│       ├── src/
│       └── tests/
└── mapping_design/
    ├── README.md
    ├── assets/
    ├── cpp/
    │   ├── CMakeLists.txt
    │   └── tools/
    └── docs/
```

## Design Blueprint Contract

`MapGenerator::to_design_blueprint()` returns `DesignBlueprint`, a native C++
record containing:

- city profile and pattern tags,
- road records with category, zone, bitmask, and asset slot,
- block records with bounds, zone, and park markers,
- lot records with building and landmark metadata,
- landmark records,
- required asset slot names for downstream sprite assignment.

## Dependencies

- C++17 compiler.
- CMake 3.16 or newer.

No runtime scripting language is required by the current source tree.
