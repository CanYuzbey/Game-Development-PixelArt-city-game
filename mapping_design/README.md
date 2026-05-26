# Mapping Design

City-design assets, sprite registry contracts, and native C++ validation and
preparation tools.

## Structure

- `assets/raw/`: original design-side source sheets.
- `assets/debug/`: contact sheets and debug images.
- `assets/asset_manifest.json`: raw-sheet manifest.
- `../assets/source_rgba/`: cleaned RGBA source sheets for runtime slicing.
- `../assets/runtime_cpp/`: C++-prepared runtime atlases.
- `../assets/manifests/runtime_registry_cpp.json`: deployable runtime sprite registry.
- `../assets/manifests/sprite_registry.json`: source slicing registry consumed by the preparer.
- `cpp/tools/asset_validator.cpp`: raw manifest and PNG signature validator.
- `cpp/tools/runtime_asset_validator.cpp`: runtime registry/atlas validator.
- `cpp/tools/runtime_asset_preparer_win.cpp`: Windows-native C++ atlas preparer.

## Runtime Asset Contract

Runtime sprites are considered game-ready when:

- `estimated` is not `true` on any sprite.
- `runtime_status` is `exported`.
- `visual_rect` is `alpha_trimmed`.
- each `atlas_rect` is inside the declared atlas PNG.
- required slots exist for terrain, roads, sidewalks, parks, buildings, roofs,
  shadows, facade kits, and landmarks.

The runtime validator enforces this deployable contract:

```bash
mapping_runtime_asset_validator assets
```

## Native Asset Preparation

On Windows, `mapping_runtime_asset_preparer` uses Windows Imaging Component
from C++:

```bash
mapping_runtime_asset_preparer assets
```

It reads `assets/source_rgba/*.png` and `assets/manifests/sprite_registry.json`,
crops every sprite by `pixel_rect`, alpha-trims non-visible pixels, adds a
4-pixel transparent guard border, procedurally generates clean orthogonal road
and sidewalk bitmask tiles, shelf-packs PNG atlases to `assets/runtime_cpp/`,
and writes `assets/manifests/runtime_registry_cpp.json`.

The prepared C++ runtime output is currently 274 sprites across 11 atlases.
The older `assets/runtime/` directory is retained for reference and comparison;
new deployable work should use `assets/runtime_cpp/`.

## Design Blueprint Bridge

The mapping algorithm exports native design data:

```cpp
#include "mapping_algorithm/map_generator.hpp"

mapping_algorithm::MapConfig config;
config.city_profile = "manhattan";

mapping_algorithm::MapGenerator generator(config);
generator.generate();

mapping_algorithm::DesignBlueprint blueprint = generator.to_design_blueprint();
```

Design and rendering code consume `DesignBlueprint::required_asset_slots`,
`buildings`, and `sprite_assignments` to bind generated city structure to the
runtime sprite registry.
