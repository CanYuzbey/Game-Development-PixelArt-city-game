# Mapping Algorithm

This folder contains the game-facing procedural mapping algorithm.

## Primary Implementation

The primary implementation is now C++17:

```text
mapping_algorithm/
  cpp/
    CMakeLists.txt
    include/mapping_algorithm/
      map_types.hpp
      map_generator.hpp
      design_blueprint.hpp
    src/
      map_generator.cpp
    examples/
      demo.cpp
    tests/
      smoke.cpp
```

The C++ code is intended for direct integration into game code. It has no
Pygame dependency, no Python runtime dependency, and exposes native structures:

- `MapConfig`
- `MapCell`
- `MapGrid`
- `MapGenerator`
- `MapStats`
- `DesignBlueprint`

## Build

```bash
cmake -S mapping_algorithm/cpp -B build/mapping_algorithm
cmake --build build/mapping_algorithm
build/mapping_algorithm/mapping_algorithm_demo
build/mapping_algorithm/mapping_algorithm_smoke
```

I could not compile locally in the current shell because no C++ compiler or
CMake executable is installed here. The project is standard CMake/C++17 and
should build in Visual Studio, CLion, Rider, Unreal build tooling, or a normal
GCC/Clang/MSVC environment.

## Relationship To Python

The root `map_builder/` Python package remains as a reference implementation,
visual demo backend, and regression oracle while the C++ version matures.

Current quality gate still runs through Python:

```bash
python tests/full_suite.py
```

The C++ port currently covers the same backend concepts at a native-library
level: coastline, elevation, zones, civic anchor, roads, sidewalks, blocks,
parks, lots, density, buildings, district names, stats, and design blueprint
export. Future work should deepen parity phase-by-phase against the Python
reference and then move tests fully native.

## Current Native API Example

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

const MapStats& stats = generator.stats();
DesignBlueprint blueprint = generator.to_design_blueprint();
```

## Verification Plan

Before considering the C++ port production-ready:

1. Compile with MSVC, Clang, and GCC.
2. Run `mapping_algorithm_smoke`.
3. Compare core metrics against Python for fixed seeds.
4. Port the 60-config quality gate to native C++.
5. Integrate with the renderer/game runtime.
