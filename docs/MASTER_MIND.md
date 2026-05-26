# Project Master Mind

## Mission

Build and preserve a deterministic native C++ procedural city generator for an
open-world RPG map. The expected output is a seed-driven city grid with
water/coastline, elevation, zones, civic anchor, highways, connector roads,
sidewalks, interior blocks, parks, lots, setbacks, building metadata,
encounter/spawn data, landmarks, density scores, district names, and design
blueprint records.

## Production Pipeline

`mapping_algorithm::MapGenerator` is the single orchestration owner:

1. Coastline
2. Elevation
3. Zones
4. Highways
5. Connectors
6. Sidewalks
7. Blocks
8. Civic anchor
9. Parks
10. Lots
11. Density post-pass
12. Lot-level building assembly and gameplay metadata
13. District naming
14. Stats

## Acceptance Contract

Primary native gate: `mapping_algorithm_smoke`.

Required result:

- 72 configs pass: 12 seeds x 6 coast modes at 80x60.
- Same seed and same config produce identical summary statistics on fresh and
  reused generator instances.
- Every accepted map has land, roads, blocks, lots, parks, spawns, and
  landmarks.
- Every accepted map has assembled building records and sprite assignments.
- Road density stays inside guard rails.
- Design blueprint export includes roads, blocks, lots, buildings, sprite
  assignments, resolved coast side, profile identity, and asset requirements.

Design asset gates: `mapping_asset_validator` and
`mapping_runtime_asset_validator`.

Required result:

- manifest schema is present and supported,
- every listed raw sheet exists,
- every listed PNG has a valid PNG signature.
- runtime registry has no estimated sprites,
- runtime registry sprites are exported and alpha-trimmed,
- runtime atlas rects stay inside atlas PNG dimensions,
- required runtime asset slots are covered.

Seed export gate: `mapping_city_exporter`.

Required result:

- one seed and map config produce a `deployable_city_map.v1` JSON file,
- JSON includes stats, roads, blocks, lots, landmarks, buildings, sprite
  assignments, and cells.

## Feedback Roles

- Architecture Feedback: pipeline shape, module boundaries, public API, config
  drift, and phase-order coupling risks.
- Customer Mapping Feedback: expected result, acceptance criteria, docs,
  city-planning believability, and gaps between promise and output.
- Optimization Feedback: pathing correctness, hotspot scans, algorithmic
  complexity, and low-risk speed/correctness improvements.
- Quality Gate Feedback: native smoke tests, deterministic checks, and asset
  validation.

## Do Not Break

- `MapGenerator::generate()` must stay deterministic.
- `MapConfig` defaults are the source of truth for native generation behavior.
- `DesignBlueprint` must stay stable enough for design and sprite assignment.
- The repository should remain a C++ source tree.
- Runtime asset slot names must match `assets/manifests/runtime_registry_cpp.json`.
