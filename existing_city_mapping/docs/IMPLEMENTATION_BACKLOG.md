# Existing City Mapping Implementation Backlog

## Needed Implementations

1. Asset pipeline
   - Slice raw generated sheets.
   - Produce RGBA sprite atlases.
   - Create debug atlases with numbered boxes.
   - Create an asset manifest from design `asset_slot` to sprite ids.

2. Design export backend
   - Keep `MapGenerator.to_design_dict()` as the stable backend contract.
   - Expand from derived road cell records to captured semantic road segments.
   - Add intersections, frontage roads, entrances, and source constraints.
   - Add optional GeoJSON-like export for design tools.

3. City profiles
   - Use `generic_dense`, `manhattan`, `barcelona_eixample`,
     `paris_haussmann`, and `london_organic` profile metadata.
   - Later, make profiles influence generation, not only export labels.
   - Add tests for profile identity: block ratio, plaza rhythm, intersections,
     waterfront behavior, and building mix.

4. Existing-city constraints
   - Add a source constraint schema for imported roads, coastlines, parks,
     landmarks, district boundaries, and locked axes.
   - Let phases consume constraints as hard or soft anchors.
   - Add snap-distance and match-strength controls.

5. Design placement algorithm
   - Use exported `blocks`, `lots`, `roads`, `landmarks`, `districts`, and
     `asset_requirements` to assign sprite families.
   - Respect zone, density, coast type, footprint style, landmark type, and
     city profile style tags.

## Needed Extra Sprites

- Diagonal road and diagonal sidewalk tile families.
- Coastal edge tile families for beach, dock, cliff, seawall, pier.
- Landmark full-building sprites or modular landmark kits.
- City-profile facade kits:
  - Manhattan/Harlem: brownstone, brick midrise, glass CBD, fire escape.
  - Barcelona: stucco, balcony rows, chamfer/courtyard corners.
  - Paris: limestone, mansard roof, boulevard storefront, civic monument.
  - London: terrace house, brick mixed-use, organic high-street shopfront.
- Small props: signs, streetlights, benches, bollards, railings, trees, planters.
- Roof and shadow overlays.

## Needed Other Things

- Naming convention for generated asset ids.
- Tile size and anchor convention.
- Manifest schema and validator.
- Pixel cleanup rules for alpha, margins, and anti-aliased edges.
- Visual regression screenshots once sprites enter the renderer.
- A small editor/debug viewer for browsing `asset_slot` assignments.
