# Seed Inspector Spec

`mapping_city_exporter` is the native C++ seed-inspection tool. It generates a
deployable JSON map for a single seed and configuration.

## Command

```bash
mapping_city_exporter \
  --seed 42 \
  --width 96 \
  --height 72 \
  --profile manhattan \
  --coast random \
  --out exports/city_seed_42.json
```

Supported coast values:

- `none`
- `north`
- `south`
- `east`
- `west`
- `random`

Supported profile ids:

- `generic_dense`
- `manhattan`
- `barcelona_eixample`
- `paris_haussmann`
- `london_organic`

## Output Schema

The output file uses `deployable_city_map.v1` and contains:

- `algorithm_version`
- `resolved_coast_side`
- `stats`
- `profile`
- `required_asset_slots`
- `roads`
- `blocks`
- `lots`
- `landmarks`
- `buildings`
- `sprite_assignments`
- `cells`

The `cells` array is intentionally complete so a developer can inspect any
coordinate and see terrain, zone, road category, block id, lot id, building
type, landmark type, footprint style, density, elevation, and encounter chance.

## Renderer Binding

Renderers should bind by `sprite_assignments` first. Each assignment points to a
target building id, the anchor cell, asset slot, sprite ids, deterministic
decision hash, and a human-readable reason string.

The `buildings` array provides the architectural explanation for each target:
footprint bounds, floors, facade family, roof type, profile-selected style, and
landmark status.
