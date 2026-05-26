# Runtime Sprite Coverage

The old missing-sprite report is obsolete. The active prepared runtime registry
now contains 274 sprites across the required city-building categories.

## Runtime Status

Authoritative registry:

```text
assets/manifests/runtime_registry_cpp.json
```

Runtime atlas directory:

```text
assets/runtime_cpp/
```

Source RGBA sheets:

```text
assets/source_rgba/
```

## Covered Slot Families

The registry currently covers the slot families required by the C++ city
generator:

- terrain exterior and water,
- diagonal and orthogonal street roads and sidewalks,
- park landscape tiles and objects,
- office, apartment, house, shop, restaurant, market, bank, and civic
  buildings,
- building roofs,
- overlay shadows,
- profile facade kits,
- town hall, station, hospital, police, and school landmarks,
- coastal, prop, overlay, and park-monument extras.

## Replacement Native Gate

Use the C++ runtime validator instead of this document for truth:

```bash
mapping_runtime_asset_validator assets
```

The validator rejects:

- estimated sprite rects,
- non-exported sprites,
- prepared sprites missing trim metadata,
- atlas rects outside PNG bounds,
- missing required runtime slot families.

## Remaining Asset Work

The next asset task is not missing coverage. It is engine integration:

1. Bind `runtime_registry_cpp.json` in the renderer.
2. Draw roads by `road_bitmask_00` through `road_bitmask_15`.
3. Draw sidewalks by `sidewalk_bitmask_00` through `sidewalk_bitmask_15`.
4. Draw buildings by `DesignBlueprint::sprite_assignments`.
