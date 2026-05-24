"""
Design-facing exports for map_builder.

This package keeps editor/backend blueprints separate from the core generation
phases. The generator remains responsible for producing the map; design exports
translate that map into stable records for tools, renderers, and city-profile
workflows.
"""
from .blueprint import CITY_PROFILES, city_profile, export_design_blueprint

__all__ = [
    "CITY_PROFILES",
    "city_profile",
    "export_design_blueprint",
]
