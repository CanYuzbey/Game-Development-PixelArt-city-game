# Existing City Mapping Asset Audit

## Raw Assets

The newly added generated PNGs were moved from `assets/` into:

`existing_city_mapping/assets/raw/`

All nine files are RGB PNG sheets at `1254x1254`. They are large generated
sprite-sheet concepts, not ready-to-use renderer sheets yet.

Debug contact sheet:

`existing_city_mapping/assets/debug/new_assets_contact_sheet.png`

## Observed Asset Groups

1. `facade_masonry_modules_raw.png`
   Facade strips, wall panels, columns, ground textures, road-like stripes.

2. `facade_arch_corner_modules_raw.png`
   Isometric roof/wall modules, arched structures, small modular details.

3. `roof_props_street_details_raw.png`
   Terrain swatches, roof pieces, props, fences, small street/decor objects.

4. `storefront_awning_modules_raw.png`
   Shopfronts, windows, doors, awnings, storefront facade slices.

5. `brownstone_apartment_facades_raw.png`
   Taller brick/stone facades, rowhouse-like fronts, gothic/arched pieces.

6. `industrial_warehouse_modules_raw.png`
   Mixed building modules, pipes, stairs, rails, small rooftop/street pieces.

7. `civic_classical_modules_raw.png`
   Civic/roof/column pieces, small architectural props, residential details.

8. `modern_glass_cbd_modules_raw.png`
   Glass/modern facade panels, office tower strips, dark CBD building pieces.

9. `damaged_urban_modules_raw.png`
   Dense mixed sheet: wall panels, fences, lamps, paving, facade pieces.

## Debug Findings

- The sheets are not on a known fixed tile grid.
- Backgrounds appear visually transparent/checkered in places, but files are RGB,
  so there is no real alpha channel yet.
- Raw filenames are not suitable for engine asset ids.
- Individual sprites need bounding boxes before they can be registered.
- Art scale is inconsistent across sheets.
- Some pieces are facade fragments rather than full isometric tiles.
- There is no manifest linking sprites to `building_type`, `zone`, `city_profile`,
  `footprint_style`, or `asset_slot`.

## Ready-To-Use Requirements

1. Convert useful sprites to RGBA with real transparency.
2. Slice sprites into stable rectangles.
3. Assign deterministic ids.
4. Normalize scale and pivot/anchor points.
5. Group sprites by asset slot:
   `building/*`, `landmark/*`, `street/*`, `road/*`, `coast/*`, `landscape/*`,
   `prop/*`.
6. Add a manifest that maps design-export `asset_slot` values to sprite ids.
7. Add debug sheets with numbered bounding boxes, matching the existing
   `roads_debug.png` and `sidewalks_debug.png` workflow.

## Extra Sprites Needed

- True road diagonal tiles and diagonal intersections.
- Shoreline transition tiles for beach, cliff, dock, seawall, and pier edges.
- Roof variants by city profile: flat roof, mansard roof, red tile roof,
  glass tower roof, rowhouse roof.
- Landmark-scale buildings: town hall, station, hospital, police, school.
- Entrances, doors, stoops, stairs, alleys, fire escapes, garage doors.
- City-profile props: Paris lamps/awnings, Barcelona balconies, London terraces,
  Manhattan fire escapes/water towers.
- Night lighting and signage overlays.
- Park objects: benches, trees, fountain, paths, playground, plaza paving.
- Building shadow/ambient occlusion overlays.
