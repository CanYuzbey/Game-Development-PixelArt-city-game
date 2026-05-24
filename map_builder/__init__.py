"""
map_builder
────────────
Public API — import only what your game needs.

    from map_builder import MapGenerator, MapConfig
    from map_builder import MapGrid, MapCell, GeneratorProgress
    from map_builder import REGISTRY          # tile registry
    from map_builder.constants import *       # tile IDs, layer constants, etc.
"""
from .map_state      import MapGrid, MapCell, MapConfig, GeneratorProgress
from .map_generator  import MapGenerator
from .tile_registry  import REGISTRY, TileDef, TileRegistry
from .constants      import (
    # Layers
    LAYER_GROUND, LAYER_ROAD, LAYER_SIDEWALK, LAYER_DECOR,
    # Road categories
    ROAD_HIGHWAY, ROAD_CONNECTOR,
    # Phases
    PHASE_COASTLINE, PHASE_HIGHWAY, PHASE_CONNECTOR,
    PHASE_SIDEWALK, PHASE_DECORATION, PHASE_COMPLETE,
    PHASE_ZONES, PHASE_ELEVATION, PHASE_BLOCKS, PHASE_PARKS, PHASE_LOTS,
    PHASE_CIVIC, PHASE_BUILDINGS,
    # Directions
    N, E, S, W,
    # Zone types
    ZONE_CBD, ZONE_MIDTOWN, ZONE_RESIDENTIAL,
    # Tile roles
    ROLE_WALKABLE_ROAD, ROLE_WALKABLE_HIGHWAY, ROLE_WALKABLE_ALLEY,
    ROLE_WALKABLE_SIDEWALK, ROLE_WALKABLE_PARK, ROLE_WALKABLE_PLAZA,
    ROLE_BUILDING_CBD, ROLE_BUILDING_MIDTOWN, ROLE_BUILDING_RESI,
    ROLE_BUILDING_CIVIC, ROLE_WATER, ROLE_EXTERIOR,
    # Coastal character types
    COAST_TYPE_NONE, COAST_TYPE_CLIFF, COAST_TYPE_BEACH, COAST_TYPE_DOCK,
    # Coastal building weights
    BEACH_BLDG_WEIGHTS, DOCK_BLDG_WEIGHTS,
    # Coastal building type constants
    BLDG_WAREHOUSE, BLDG_PIER, BLDG_RESORT, BLDG_BEACH_BAR,
)

__all__ = [
    'MapGenerator', 'MapConfig',
    'MapGrid', 'MapCell', 'GeneratorProgress',
    'REGISTRY', 'TileDef', 'TileRegistry',
    'LAYER_GROUND', 'LAYER_ROAD', 'LAYER_SIDEWALK', 'LAYER_DECOR',
    'ROAD_HIGHWAY', 'ROAD_CONNECTOR',
    'PHASE_COASTLINE', 'PHASE_HIGHWAY', 'PHASE_CONNECTOR',
    'PHASE_SIDEWALK', 'PHASE_DECORATION', 'PHASE_COMPLETE',
    'PHASE_ZONES', 'PHASE_ELEVATION', 'PHASE_BLOCKS', 'PHASE_PARKS', 'PHASE_LOTS',
    'PHASE_CIVIC', 'PHASE_BUILDINGS',
    'N', 'E', 'S', 'W',
    'ZONE_CBD', 'ZONE_MIDTOWN', 'ZONE_RESIDENTIAL',
    'ROLE_WALKABLE_ROAD', 'ROLE_WALKABLE_HIGHWAY', 'ROLE_WALKABLE_ALLEY',
    'ROLE_WALKABLE_SIDEWALK', 'ROLE_WALKABLE_PARK', 'ROLE_WALKABLE_PLAZA',
    'ROLE_BUILDING_CBD', 'ROLE_BUILDING_MIDTOWN', 'ROLE_BUILDING_RESI',
    'ROLE_BUILDING_CIVIC', 'ROLE_WATER', 'ROLE_EXTERIOR',
    'COAST_TYPE_NONE', 'COAST_TYPE_CLIFF', 'COAST_TYPE_BEACH', 'COAST_TYPE_DOCK',
    'BEACH_BLDG_WEIGHTS', 'DOCK_BLDG_WEIGHTS',
    'BLDG_WAREHOUSE', 'BLDG_PIER', 'BLDG_RESORT', 'BLDG_BEACH_BAR',
]
