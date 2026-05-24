# Mapping Design

This folder owns city-design data that sits on top of the native mapping
algorithm: existing-city profiles, raw/sliced assets, sprite manifests, and
design validation tools.

## Structure

- `assets/raw/`: source PNG sheets from the latest asset drop.
- `assets/debug/`: contact sheets and debug atlases.
- `assets/asset_manifest.json`: raw-sheet manifest and candidate slot mapping.
- `docs/ASSET_AUDIT.md`: asset readiness findings and missing sprite list.
- `docs/IMPLEMENTATION_BACKLOG.md`: implementation, sprite, and tooling backlog.
- `cpp/tools/asset_validator.cpp`: native manifest and PNG-presence validator.

## Backend Bridge

The mapping algorithm exports native design data:

```cpp
#include "mapping_algorithm/map_generator.hpp"

mapping_algorithm::MapConfig config;
config.city_profile = "manhattan";

mapping_algorithm::MapGenerator generator(config);
generator.generate();

mapping_algorithm::DesignBlueprint blueprint = generator.to_design_blueprint();
```

Design code consumes `DesignBlueprint` and maps each asset slot to prepared
sprites in `assets/asset_manifest.json`.

## Asset Status

The current raw sheets are not runtime-ready. They are RGB sheets with baked
checkerboard backgrounds and no real alpha channel. They must be sliced,
cleaned, alpha-converted, scaled, named, and registered before runtime use.

Run the native validator after building:

```bash
build/mapping_design/cpp/mapping_asset_validator mapping_design/assets
```

Expected current result: manifest OK and all listed raw PNG sheets present.
