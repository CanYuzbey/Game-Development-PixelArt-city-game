# Mapping Algorithm

Native C++17 procedural city generation and deployable map export.

## Structure

```text
mapping_algorithm/
  cpp/
    CMakeLists.txt
    include/mapping_algorithm/
      design_blueprint.hpp
      map_generator.hpp
      map_types.hpp
    src/map_generator.cpp
    examples/demo.cpp
    tests/smoke.cpp
    tools/city_exporter.cpp
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
- 6 coast modes, including deterministic resolution of `random`.
- repeat generation on fresh and reused generator instances.
- anatomy checks for land, roads, blocks, lots, parks, spawns, landmarks, and
  buildings.
- road-density guard rails.
- blueprint checks for roads, blocks, lots, buildings, sprite assignments,
  normalized asset slots, and profile identity.
- invalid-config rejection checks.

## Export Tool

`mapping_city_exporter` writes a deployable JSON file for a seed:

```bash
mapping_city_exporter --seed 7 --profile manhattan --coast west --out exports/seed_7.json
```

The JSON includes the resolved city design, every assembled building, every
sprite assignment, and every cell's gameplay/design metadata.

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
- `MapStats`: generation summary, including building count.
- `BuildingAssemblyRecord`: lot-level building result with footprint, floors,
  facade/roof selection, asset slot, and sprite stack.
- `SpriteAssignmentRecord`: renderer-facing sprite stack assigned to a generated
  target.
- `DesignBlueprint`: design-facing export for profile, roads, blocks, lots,
  landmarks, buildings, sprite assignments, and required asset slots.
