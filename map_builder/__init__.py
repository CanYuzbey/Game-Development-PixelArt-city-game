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
    # Directions
    N, E, S, W,
)

__all__ = [
    'MapGenerator', 'MapConfig',
    'MapGrid', 'MapCell', 'GeneratorProgress',
    'REGISTRY', 'TileDef', 'TileRegistry',
    'LAYER_GROUND', 'LAYER_ROAD', 'LAYER_SIDEWALK', 'LAYER_DECOR',
    'ROAD_HIGHWAY', 'ROAD_CONNECTOR',
    'PHASE_COASTLINE', 'PHASE_HIGHWAY', 'PHASE_CONNECTOR',
    'PHASE_SIDEWALK', 'PHASE_DECORATION', 'PHASE_COMPLETE',
    'N', 'E', 'S', 'W',
]
