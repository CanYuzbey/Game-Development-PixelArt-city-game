# Building Assembly Spec

The generator now creates buildings per lot, not per cell. A building is a
deterministic assembly record that can be inspected, serialized, and rendered
from sprite stacks.

## Inputs

For each generated lot, the assembly pass reads:

- lot cells after road, sidewalk, block, park, and civic-anchor passes,
- dominant zone,
- waterfront/coast adjacency,
- city profile,
- seed and lot id,
- explicit landmark assignment, if any.

Sidewalk cells stay sidewalks and are excluded from the buildable footprint.

## Landmark Selection

The civic anchor lot becomes `town_hall` when it has a valid lot id.

Additional landmark lots are selected by deterministic seed hash:

- `station`
- `hospital`
- `police`
- `school`

These records use `landmark/*` asset slots and landmark sprite variants.

## Building Type Selection

Normal lots choose type by zone and waterfront state:

- CBD: office, bank, or civic.
- Midtown: apartment, shop, or restaurant.
- Residential: house, apartment, or small shop.
- Waterfront: restaurant, market, apartment, or open exterior.

The selection is deterministic and based on `master_seed`, `lot_id`, lot area,
and the building salt.

## Footprint And Floors

Residential house lots with enough area use perimeter setbacks. Other lots use
the available buildable footprint. Each `BuildingAssemblyRecord` stores:

- lot id and block id,
- anchor cell,
- footprint bounds,
- floor count,
- zone,
- building type and optional landmark type,
- footprint style,
- facade family,
- roof type,
- asset slot,
- sprite stack.

Floor ranges are tuned by type:

- offices: 7-16 floors,
- CBD apartments: 5-9 floors,
- mid/residential apartments: 3-6 floors,
- banks/civic: 3-5 floors,
- hospital/police/station: 2-4 floors,
- shops, restaurants, markets, houses, schools: 1-3 floors.

## Sprite Stack

Each building receives a renderer-facing stack:

1. shadow sprite,
2. building or landmark base sprite,
3. roof sprite for non-landmark buildings,
4. optional profile kit overlay such as fire escapes, balconies, or bay windows.

The stack is exported through `DesignBlueprint::sprite_assignments`.
