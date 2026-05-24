# Mapping Design

This folder owns design-facing map work: existing-city profiles, raw/sliced
assets, sprite manifests, design export requirements, and future editor tools.

It is deliberately separate from `mapping_algorithm/`, which owns the native
generator implementation.

## Structure

- `assets/raw/`: renamed source PNG sheets from the newest asset drop.
- `assets/debug/`: contact sheets and future numbered debug atlases.
- `assets/asset_manifest.json`: current raw-sheet manifest and candidate slots.
- `docs/ASSET_AUDIT.md`: asset readiness findings and missing sprite list.
- `docs/IMPLEMENTATION_BACKLOG.md`: implementation, sprite, and tooling backlog.
- `tools/validate_assets.py`: manifest and raw-sheet validator.

## Backend Bridge

The Python reference generator exposes a design blueprint:

```python
from map_builder import MapConfig, MapGenerator

gen = MapGenerator(MapConfig(city_profile="manhattan"))
gen.generate_blocking()
blueprint = gen.to_design_dict(include_cells=False)
```

The C++ implementation exposes the parallel native structure:

```cpp
#include "mapping_algorithm/map_generator.hpp"

mapping_algorithm::MapConfig config;
config.city_profile = "manhattan";
mapping_algorithm::MapGenerator generator(config);
generator.generate();
mapping_algorithm::DesignBlueprint blueprint = generator.to_design_blueprint();
```

## Asset Status

The current raw sheets are not runtime-ready. They are RGB sheets with baked
checkerboard backgrounds and no real alpha channel. They must be sliced,
cleaned, alpha-converted, scaled, named, and registered before runtime use.

Run the validator:

```bash
python mapping_design/tools/validate_assets.py
```

Expected current result: manifest OK with no-alpha warnings.
