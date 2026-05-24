# Existing City Mapping

This folder owns the current task: turning generated mapping data into
existing-city-inspired design output.

## Structure

- `assets/raw/`: renamed source PNG sheets from the new asset drop.
- `assets/debug/`: contact sheets and future numbered debug atlases.
- `assets/asset_manifest.json`: current raw-sheet manifest and candidate slots.
- `docs/ASSET_AUDIT.md`: asset readiness findings and missing sprite list.
- `docs/IMPLEMENTATION_BACKLOG.md`: implementation, sprite, and tooling backlog.
- `tools/validate_assets.py`: manifest and raw-sheet validator.

## Backend Bridge

The generator now exposes:

```python
from map_builder import MapConfig, MapGenerator

gen = MapGenerator(MapConfig(city_profile="manhattan"))
gen.generate_blocking()
blueprint = gen.to_design_dict(include_cells=False)
```

The returned blueprint is a design/backend structure for tools and renderers:
profile, config, metrics, roads, blocks, lots, landmarks, districts, and asset
requirements.
