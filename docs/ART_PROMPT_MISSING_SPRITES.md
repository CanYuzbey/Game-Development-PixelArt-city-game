# Future Runtime Sprite Art Direction

The current runtime sprite registry is populated. This document is retained as
future art direction, not as a missing-sprite checklist.

## Technical Rules

- Projection: isometric 2:1 pixel ratio.
- Runtime format: RGBA PNG with true transparency.
- Sprite preparation: alpha-trim visible art and add transparent guard padding.
- Edge rule: no label text, bounding boxes, checkerboard pixels, white matte, or
  opaque garbage pixels may survive in the runtime atlas.
- Lighting: consistent top-left light source.
- Palette: desaturated urban colors, readable materials, hard pixel edges.
- Runtime registry: every new sprite must include `pixel_rect`, `asset_slot`,
  `atlas_file`, `atlas_rect`, `runtime_status: "exported"`, and
  `visual_rect: "alpha_trimmed"`.

## Building Art Rules

Buildings are assembled from sprite stacks:

1. shadow,
2. base building or landmark,
3. roof for non-landmark buildings,
4. optional facade/profile kit.

New art must support the existing generator slot families:

- `building/office`
- `building/apartment`
- `building/house`
- `building/shop`
- `building/restaurant`
- `building/market`
- `building/bank`
- `building/civic`
- `building/roof`
- `overlay/shadow`
- `prop/facade_kit`
- `landmark/town_hall`
- `landmark/station`
- `landmark/hospital`
- `landmark/police`
- `landmark/school`

## Validation

Future asset drops must pass:

```bash
mapping_runtime_asset_preparer assets
mapping_runtime_asset_validator assets
```

The preparer is the C++ path for cleaning, packing, and generating the
orthogonal road/sidewalk bitmask tiles. The validator is the gate for
deployable runtime assets.
