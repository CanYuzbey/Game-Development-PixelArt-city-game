# Mapping Algorithm

This folder contains the native C++17 procedural city generator.

## Structure

```text
mapping_algorithm/
  cpp/
    CMakeLists.txt
    include/mapping_algorithm/
      design_blueprint.hpp
      map_generator.hpp
      map_types.hpp
    src/
      map_generator.cpp
    examples/
      demo.cpp
    tests/
      smoke.cpp
```

## Build

From the repository root:

```bash
cmake -S . -B build
cmake --build build
```

Or build this module alone:

```bash
cmake -S mapping_algorithm/cpp -B build/mapping_algorithm
cmake --build build/mapping_algorithm
```

## Quality Gate

`mapping_algorithm_smoke` runs the native deterministic gate:

- 12 seeds.
- 5 coast modes.
- repeated generation per config to verify determinism.
- city anatomy checks for land, roads, blocks, lots, parks, spawns, landmarks.
- design blueprint checks for roads, blocks, lots, asset requirements, and profile
  identity.

## API Example

```cpp
#include "mapping_algorithm/map_generator.hpp"

using namespace mapping_algorithm;

MapConfig config;
config.width = 80;
config.height = 60;
config.master_seed = 7;
config.coast_side = CoastSide::West;
config.city_profile = "manhattan";

MapGenerator generator(config);
generator.generate();

const MapGrid& grid = generator.grid();
const MapStats& stats = generator.stats();
DesignBlueprint blueprint = generator.to_design_blueprint();
```

## Native Data Types

- `MapConfig`: generation inputs and tuning knobs.
- `MapCell`: per-cell terrain, road, zone, lot, building, encounter, and design
  metadata.
- `MapGrid`: fixed-size city grid with road and sidewalk helpers.
- `MapStats`: generation summary.
- `DesignBlueprint`: design-facing export for city profile, roads, blocks, lots,
  landmarks, and required asset slots.
