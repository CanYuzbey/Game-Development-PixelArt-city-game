# Runtime Asset Registry Spec

The production runtime registry is
`assets/manifests/runtime_registry_cpp.json`. It is the bridge between generated
city records and packed atlas sprites.

`assets/manifests/sprite_registry.json` remains the source slicing registry
consumed by the C++ preparer.

## Required Sprite Fields

Each sprite entry must provide:

- `source_sheet`: basename under `assets/source_rgba/`.
- `pixel_rect`: `[x, y, w, h]` source crop in RGBA source-sheet pixels.
- `asset_slot`: renderer contract slot, for example `building/office`.
- `runtime_status`: must be `exported`.
- `atlas_file`: PNG filename under `assets/runtime_cpp/`.
- `atlas_rect`: `[x, y, w, h]` packed atlas rect.
- `visual_rect`: must be `alpha_trimmed`.

No sprite may keep `"estimated": true`.

## Required Slot Families

The C++ generator expects these slot families to exist:

- `terrain/exterior`
- `terrain/water`
- `street/road`
- `street/sidewalk`
- `landscape/park`
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

## No-Boundary-Pixel Rule

Prepared runtime sprites must not carry source labels, detection boxes, baked
checkerboard, or opaque boundary pixels around the visual art. The native
preparer enforces this by:

- reading only `assets/source_rgba` sheets,
- cropping by curated `pixel_rect`,
- alpha-trimming to visible pixels,
- adding a transparent 4-pixel guard border,
- writing new atlas rects from the cleaned padded image.

## Native Gates

Run these after asset changes:

```bash
mapping_runtime_asset_preparer assets
mapping_runtime_asset_validator assets
```

`mapping_runtime_asset_preparer` also creates C++ procedural
`road_bitmask_00` through `road_bitmask_15` and `sidewalk_bitmask_00` through
`sidewalk_bitmask_15` sprites. These replace the old RGB road/sidewalk fallback
with transparent, guard-padded runtime tiles.

`mapping_runtime_asset_validator` checks registry status, atlas existence, PNG
headers, atlas bounds, required slot coverage, and prepared trim metadata.
