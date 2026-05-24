"""
map_builder/design/blueprint.py
--------------------------------
Design-facing export layer for turning generated map data into city layouts.

The generator owns procedural structure. This module translates that structure
into stable, renderer/tool friendly records: roads, blocks, lots, landmarks,
districts, and asset hints. It is intentionally pure data: no Pygame, no image
loading, and no renderer assumptions beyond grid coordinates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Iterable

from ..constants import (
    ROAD_CONNECTOR,
    ROAD_HIGHWAY,
    ZONE_CBD,
    ZONE_MIDTOWN,
    ZONE_RESIDENTIAL,
)

if TYPE_CHECKING:
    from .map_generator import MapGenerator
    from .map_state import MapGrid


SCHEMA_VERSION = "city_design_blueprint.v1"

ZONE_LABELS = {
    ZONE_CBD: "cbd",
    ZONE_MIDTOWN: "midtown",
    ZONE_RESIDENTIAL: "residential",
}


@dataclass(frozen=True)
class CityProfile:
    """Design preset metadata for matching generated maps to existing cities."""

    id: str
    label: str
    street_pattern: str
    block_ratio: str
    coast_bias: str
    config_overrides: dict
    design_tags: tuple[str, ...]
    asset_style_tags: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


CITY_PROFILES: dict[str, CityProfile] = {
    "generic_dense": CityProfile(
        id="generic_dense",
        label="Generic Dense City",
        street_pattern="orthogonal_grid_with_soft_drift",
        block_ratio="2.0:1",
        coast_bias="optional",
        config_overrides={},
        design_tags=("balanced", "mixed_density", "gameplay_ready"),
        asset_style_tags=("neutral_facade", "mixed_urban", "generic_props"),
    ),
    "manhattan": CityProfile(
        id="manhattan",
        label="Manhattan / Harlem",
        street_pattern="long_avenues_short_cross_streets_diagonal",
        block_ratio="3.4:1",
        coast_bias="river_edges",
        config_overrides={
            "avenue_spacing": 27,
            "connector_spacing": 8,
            "diagonal_streets": 2,
            "roundabout_count": 2,
        },
        design_tags=("avenue_grid", "waterfront_edges", "brownstone_midrise"),
        asset_style_tags=("brick_facade", "brownstone", "glass_cbd"),
    ),
    "barcelona_eixample": CityProfile(
        id="barcelona_eixample",
        label="Barcelona Eixample",
        street_pattern="regular_square_grid_chamfered_blocks",
        block_ratio="1.1:1",
        coast_bias="seafront_axis",
        config_overrides={
            "avenue_spacing": 12,
            "connector_spacing": 11,
            "diagonal_streets": 0,
            "roundabout_count": 8,
        },
        design_tags=("square_grid", "chamfered_corners", "courtyard_blocks"),
        asset_style_tags=("stucco_facade", "balcony_rows", "courtyard_midrise"),
    ),
    "paris_haussmann": CityProfile(
        id="paris_haussmann",
        label="Paris Haussmann",
        street_pattern="boulevard_grid_with_diagonals",
        block_ratio="1.5:1",
        coast_bias="river_axis",
        config_overrides={
            "avenue_spacing": 18,
            "connector_spacing": 12,
            "diagonal_streets": 2,
            "roundabout_count": 6,
        },
        design_tags=("boulevard", "monument_axis", "courtyard_blocks"),
        asset_style_tags=("stone_facade", "mansard_roof", "civic_limestone"),
    ),
    "london_organic": CityProfile(
        id="london_organic",
        label="London Organic",
        street_pattern="irregular_grid_low_drift",
        block_ratio="1.6:1",
        coast_bias="river_axis",
        config_overrides={
            "avenue_spacing": 14,
            "connector_spacing": 9,
            "connector_turn_bias": 0.20,
            "diagonal_streets": 0,
            "roundabout_count": 4,
        },
        design_tags=("irregular_blocks", "mixed_scale", "park_squares"),
        asset_style_tags=("brick_facade", "terrace_house", "stone_civic"),
    ),
}


def city_profile(profile_id: str | None) -> CityProfile:
    """Return a known city profile, falling back to the neutral dense profile."""
    if not profile_id:
        return CITY_PROFILES["generic_dense"]
    return CITY_PROFILES.get(profile_id, CITY_PROFILES["generic_dense"])


def _bbox(cells: Iterable[tuple[int, int]]) -> dict:
    points = list(cells)
    if not points:
        return {"r0": 0, "c0": 0, "r1": 0, "c1": 0, "width": 0, "height": 0}
    rows = [r for r, _ in points]
    cols = [c for _, c in points]
    r0, r1 = min(rows), max(rows)
    c0, c1 = min(cols), max(cols)
    return {
        "r0": r0,
        "c0": c0,
        "r1": r1,
        "c1": c1,
        "width": c1 - c0 + 1,
        "height": r1 - r0 + 1,
    }


def _centroid(cells: Iterable[tuple[int, int]]) -> dict:
    points = list(cells)
    if not points:
        return {"r": 0.0, "c": 0.0}
    return {
        "r": round(sum(r for r, _ in points) / len(points), 3),
        "c": round(sum(c for _, c in points) / len(points), 3),
    }


def _majority(values: Iterable) -> object:
    counts: dict = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], str(item[0])))[0]


def _cell_records(grid: "MapGrid") -> list[dict]:
    cells: list[dict] = []
    for r, c, cell in grid.all_cells():
        cells.append(
            {
                "r": r,
                "c": c,
                "role": cell.tile_role,
                "zone": ZONE_LABELS.get(cell.zone_id, "unassigned"),
                "road": cell.road_category or "",
                "block_id": cell.block_id,
                "lot_id": cell.lot_id,
                "building_type": cell.building_type,
                "landmark_type": cell.landmark_type,
                "district": cell.district_name,
                "density": round(cell.density_score, 3),
                "elevation": round(cell.elevation, 3),
                "coast_type": cell.coast_type,
                "is_park": cell.is_park,
                "is_setback": cell.is_setback,
                "footprint_style": cell.footprint_style,
                "asset_slot": _asset_slot_for_cell(cell),
            }
        )
    return cells


def _asset_slot_for_cell(cell) -> str:
    if cell.landmark_type:
        return f"landmark/{cell.landmark_type}"
    if cell.is_park:
        return "landscape/park"
    if cell.is_water:
        return "terrain/water"
    if cell.road_category == ROAD_HIGHWAY:
        return "road/highway"
    if cell.road_category == ROAD_CONNECTOR:
        return "road/connector"
    if cell.is_sidewalk:
        return "street/sidewalk"
    if cell.building_type:
        return f"building/{cell.building_type}"
    if cell.coast_type:
        return f"coast/{cell.coast_type}"
    return "terrain/exterior"


def _road_records(grid: "MapGrid") -> list[dict]:
    roads: list[dict] = []
    for r, c, cell in grid.all_cells():
        if not cell.is_road:
            continue
        mask = grid.road_bitmask(r, c)
        roads.append(
            {
                "r": r,
                "c": c,
                "category": cell.road_category,
                "bitmask": mask,
                "tile_id": cell.layers.get(1),
                "zone": ZONE_LABELS.get(cell.zone_id, "unassigned"),
                "district": cell.district_name,
                "is_intersection": bin(mask).count("1") >= 3,
                "asset_slot": (
                    "road/highway"
                    if cell.road_category == ROAD_HIGHWAY
                    else "road/connector"
                ),
            }
        )
    return roads


def _block_records(generator: "MapGenerator") -> list[dict]:
    records: list[dict] = []
    for block_index, block_cells in enumerate(generator.blocks):
        if not block_cells:
            continue
        zones = [generator.grid[r][c].zone_id for r, c in block_cells]
        districts = [generator.grid[r][c].district_name for r, c in block_cells]
        first_r, first_c = sorted(block_cells)[0]
        first = generator.grid[first_r][first_c]
        records.append(
            {
                "id": first.block_id if first.block_id >= 0 else block_index,
                "area": len(block_cells),
                "bbox": _bbox(block_cells),
                "centroid": _centroid(block_cells),
                "zone": ZONE_LABELS.get(_majority(zones), "unassigned"),
                "district": _majority(districts) or "",
                "is_park": any(generator.grid[r][c].is_park for r, c in block_cells),
                "design_tags": _block_tags(generator.grid, block_cells),
            }
        )
    return records


def _lot_records(generator: "MapGenerator") -> list[dict]:
    records: list[dict] = []
    for lot_index, lot_cells in enumerate(generator.lots):
        if not lot_cells:
            continue
        zones = [generator.grid[r][c].zone_id for r, c in lot_cells]
        btypes = [generator.grid[r][c].building_type for r, c in lot_cells if generator.grid[r][c].building_type]
        landmarks = [generator.grid[r][c].landmark_type for r, c in lot_cells if generator.grid[r][c].landmark_type]
        first_r, first_c = sorted(lot_cells)[0]
        first = generator.grid[first_r][first_c]
        records.append(
            {
                "id": first.lot_id if first.lot_id >= 0 else lot_index,
                "block_id": first.block_id,
                "area": len(lot_cells),
                "bbox": _bbox(lot_cells),
                "centroid": _centroid(lot_cells),
                "zone": ZONE_LABELS.get(_majority(zones), "unassigned"),
                "building_type": _majority(btypes) or "",
                "landmark_type": _majority(landmarks) or "",
                "footprint_style": first.footprint_style or "solid",
                "has_setback": any(generator.grid[r][c].is_setback for r, c in lot_cells),
                "asset_slot": (
                    f"landmark/{_majority(landmarks)}"
                    if landmarks
                    else f"building/{_majority(btypes) or 'empty_lot'}"
                ),
                "design_tags": _lot_tags(generator.grid, lot_cells),
            }
        )
    return records


def _landmark_records(grid: "MapGrid") -> list[dict]:
    by_type: dict[str, list[tuple[int, int]]] = {}
    for r, c, cell in grid.all_cells():
        if cell.landmark_type:
            by_type.setdefault(cell.landmark_type, []).append((r, c))
    return [
        {
            "type": ltype,
            "bbox": _bbox(cells),
            "centroid": _centroid(cells),
            "asset_slot": f"landmark/{ltype}",
        }
        for ltype, cells in sorted(by_type.items())
    ]


def _district_records(generator: "MapGenerator") -> list[dict]:
    districts = generator.stats.get("districts", [])
    return [dict(district) for district in districts]


def _block_tags(grid: "MapGrid", cells: set[tuple[int, int]]) -> list[str]:
    tags: set[str] = set()
    if any(grid[r][c].is_park for r, c in cells):
        tags.add("open_space")
    if any(grid.cell(r + dr, c + dc) is not None and grid.cell(r + dr, c + dc).is_water
           for r, c in cells for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))):
        tags.add("waterfront")
    bbox = _bbox(cells)
    if bbox["height"] and bbox["width"] / max(bbox["height"], 1) >= 2.5:
        tags.add("long_block")
    if bbox["width"] and bbox["height"] / max(bbox["width"], 1) >= 2.5:
        tags.add("deep_block")
    return sorted(tags)


def _lot_tags(grid: "MapGrid", cells: set[tuple[int, int]]) -> list[str]:
    tags: set[str] = set()
    if any(grid[r][c].is_setback for r, c in cells):
        tags.add("setback")
    if any(grid[r][c].coast_type for r, c in cells):
        tags.add("coastal")
    if any(grid[r][c].landmark_type for r, c in cells):
        tags.add("landmark")
    if any(grid[r][c].footprint_style == "courtyard" for r, c in cells):
        tags.add("courtyard")
    if any(grid[r][c].footprint_style == "lshape" for r, c in cells):
        tags.add("lshape")
    return sorted(tags)


def _asset_requirements(profile: CityProfile) -> dict:
    return {
        "required_slots": [
            "terrain/water",
            "terrain/exterior",
            "road/highway",
            "road/connector",
            "street/sidewalk",
            "landscape/park",
            "building/office",
            "building/shop",
            "building/apartment",
            "building/house",
            "building/restaurant",
            "building/market",
            "building/school",
            "building/hospital",
            "building/police",
            "landmark/town_hall",
            "landmark/station",
            "landmark/hospital",
            "landmark/police",
            "landmark/school",
            "coast/beach",
            "coast/dock",
            "coast/cliff",
        ],
        "profile_style_tags": list(profile.asset_style_tags),
        "missing_from_new_assets": [
            "transparent_32_or_64px_tile_grid",
            "road_diagonal_true_tiles",
            "shoreline_transition_tiles",
            "roof_variants",
            "night_lighting_overlays",
            "building_entrance_markers",
        ],
    }


def export_design_blueprint(
    generator: "MapGenerator",
    profile_id: str | None = None,
    include_cells: bool = True,
) -> dict:
    """
    Export generated city data as a stable design/backend blueprint.

    Call after `generator.generate_blocking()` or after the generator is
    exhausted. The structure is suitable for renderers, city-profile matching,
    sprite assignment, and future real-city import/adaptation tools.
    """
    profile = city_profile(profile_id)
    grid = generator.grid
    blueprint = {
        "schema": SCHEMA_VERSION,
        "profile": profile.to_dict(),
        "config": generator.to_dict()["config"],
        "metrics": dict(generator.stats),
        "coordinate_system": {
            "origin": "top_left",
            "unit": "cell",
            "meters_per_cell": 10,
            "width": grid.width,
            "height": grid.height,
        },
        "districts": _district_records(generator),
        "roads": _road_records(grid),
        "blocks": _block_records(generator),
        "lots": _lot_records(generator),
        "landmarks": _landmark_records(grid),
        "asset_requirements": _asset_requirements(profile),
    }
    if include_cells:
        blueprint["cells"] = _cell_records(grid)
    return blueprint
