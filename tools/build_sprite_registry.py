#!/usr/bin/env python3
"""
tools/build_sprite_registry.py
================================
Builds assets/manifests/sprite_registry.json from detected_regions.json
plus the manual sprite-ID mapping defined in this file.

For sheets where individual sprites were cleanly detected (terrain_ground,
building_overlays, park_objects, street_props) the pixel_rects come directly
from the detector. For sheets where rows were merged by the dilation pass,
rects are either individually detected (first sprites in the row) or estimated
by equal-width splitting of the merged region (marked with "estimated": true).

Run after debug_sprites.py:
    python tools/build_sprite_registry.py
"""

import json
import os

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFESTS    = os.path.join(ROOT, "assets", "manifests")
DETECTED_JSON = os.path.join(MANIFESTS, "detected_regions.json")
OUT_JSON     = os.path.join(MANIFESTS, "sprite_registry.json")

# ── Helpers ────────────────────────────────────────────────────────────────────

def reg(sheet_data, idx):
    """Return pixel_rect list for region index idx in sheet_data."""
    return sheet_data["regions"][idx]["pixel_rect"]

def split_h(rect, n):
    """Split rect horizontally into n equal slices. Returns list of rects."""
    x, y, w, h = rect
    sw = w // n
    return [[x + i * sw, y, sw, h] for i in range(n)]

def split_v(rect, n):
    """Split rect vertically into n equal slices. Returns list of rects."""
    x, y, w, h = rect
    sh = h // n
    return [[x, y + i * sh, w, sh] for i in range(n)]

def entry(source_sheet, pixel_rect, asset_slot, condition="clean",
          city_profile=None, estimated=False):
    e = {
        "source_sheet": source_sheet,
        "pixel_rect": pixel_rect,
        "asset_slot": asset_slot,
        "condition": condition,
        "runtime_status": "pending_alpha_conversion",
    }
    if city_profile:
        e["city_profile"] = city_profile
    if estimated:
        e["estimated"] = True
    return e


# ── Sprite mapping definition ─────────────────────────────────────────────────

def build_registry(detected):
    S = detected["sheets"]
    sprites = {}

    # ── TERRAIN GROUND  (terrain_ground, 20 individually detected tiles) ──────
    TG = S["terrain_ground"]
    r = lambda i: reg(TG, i)
    sprites["ground_land"]                  = entry("terrain_ground", r(0),  "terrain/exterior", "clean")
    sprites["ground_land_weathered"]        = entry("terrain_ground", r(1),  "terrain/exterior", "weathered")
    sprites["ground_water"]                 = entry("terrain_ground", r(2),  "terrain/water",    "clean")
    sprites["ground_water_shimmer"]         = entry("terrain_ground", r(3),  "terrain/water",    "animated")
    sprites["ground_land_alt_a"]            = entry("terrain_ground", r(4),  "terrain/exterior", "clean")
    sprites["ground_land_alt_a_weathered"]  = entry("terrain_ground", r(5),  "terrain/exterior", "weathered")
    sprites["ground_land_alt_b"]            = entry("terrain_ground", r(6),  "terrain/exterior", "clean")
    sprites["ground_land_alt_b_weathered"]  = entry("terrain_ground", r(7),  "terrain/exterior", "weathered")
    sprites["ground_park_grass"]            = entry("terrain_ground", r(8),  "landscape/park",   "clean")
    sprites["ground_park_grass_weathered"]  = entry("terrain_ground", r(9),  "landscape/park",   "weathered")
    sprites["ground_park_grass_b"]          = entry("terrain_ground", r(10), "landscape/park",   "clean")
    sprites["ground_park_grass_b_weathered"]= entry("terrain_ground", r(11), "landscape/park",   "weathered")
    sprites["ground_plaza_paving"]          = entry("terrain_ground", r(12), "terrain/exterior", "clean")
    sprites["ground_plaza_paving_weathered"]= entry("terrain_ground", r(13), "terrain/exterior", "weathered")
    sprites["ground_plaza_alt"]             = entry("terrain_ground", r(14), "terrain/exterior", "clean")
    sprites["ground_plaza_alt_weathered"]   = entry("terrain_ground", r(15), "terrain/exterior", "weathered")
    sprites["ground_inset_a"]               = entry("terrain_ground", r(16), "terrain/exterior", "clean")
    sprites["ground_inset_b"]               = entry("terrain_ground", r(17), "terrain/exterior", "clean")
    sprites["ground_inset_c"]               = entry("terrain_ground", r(18), "terrain/exterior", "weathered")
    sprites["ground_inset_d"]               = entry("terrain_ground", r(19), "terrain/exterior", "weathered")

    # ── BUILDINGS ─────────────────────────────────────────────────────────────
    BD = S["buildings"]
    r = lambda i: reg(BD, i)

    # CBD row — all 5 individually detected
    sprites["bldg_cbd_glass_a"]     = entry("buildings", r(0), "building/office", "clean")
    sprites["bldg_cbd_glass_b"]     = entry("buildings", r(1), "building/office", "clean")
    sprites["bldg_cbd_brick_a"]     = entry("buildings", r(2), "building/office", "clean")
    sprites["bldg_cbd_concrete_a"]  = entry("buildings", r(3), "building/office", "clean")
    sprites["bldg_cbd_corner_glass"]= entry("buildings", r(4), "building/office", "clean")

    # Mid-rise — first 2 individual, last 4 estimated from merged region [7]
    sprites["bldg_mid_brownstone_a"]  = entry("buildings", r(5), "building/apartment", "clean")
    sprites["bldg_mid_brownstone_b"]  = entry("buildings", r(6), "building/apartment", "weathered")
    mid_merged = split_h(r(7), 4)
    sprites["bldg_mid_brick_a"]       = entry("buildings", mid_merged[0], "building/apartment", "clean",    estimated=True)
    sprites["bldg_mid_brick_b"]       = entry("buildings", mid_merged[1], "building/apartment", "clean",    estimated=True)
    sprites["bldg_mid_stucco_a"]      = entry("buildings", mid_merged[2], "building/apartment", "clean",    city_profile="barcelona_eixample", estimated=True)
    sprites["bldg_mid_limestone_a"]   = entry("buildings", mid_merged[3], "building/apartment", "clean",    city_profile="paris_haussmann",    estimated=True)

    # Residential — two merged groups
    resi_left  = split_h(r(8), 3)
    resi_right = split_h(r(9), 2)
    sprites["bldg_resi_rowhouse_a"]   = entry("buildings", resi_left[0],  "building/house", "clean",    estimated=True)
    sprites["bldg_resi_rowhouse_b"]   = entry("buildings", resi_left[1],  "building/house", "clean",    estimated=True)
    sprites["bldg_resi_terrace_a"]    = entry("buildings", resi_left[2],  "building/house", "clean",    city_profile="london_organic", estimated=True)
    sprites["bldg_resi_detached_a"]   = entry("buildings", resi_right[0], "building/house", "clean",    estimated=True)
    sprites["bldg_resi_detached_b"]   = entry("buildings", resi_right[1], "building/house", "clean",    estimated=True)

    # Commercial — estimated from merged region [10], split into 4 top + 2 bottom
    x10, y10, w10, h10 = r(10)
    row_h = h10 // 2
    comm_top = split_h([x10, y10, w10, row_h], 4)
    sprites["bldg_shop_storefront_a"] = entry("buildings", comm_top[0], "building/shop",       "clean", estimated=True)
    sprites["bldg_shop_storefront_b"] = entry("buildings", comm_top[1], "building/shop",       "clean", estimated=True)
    sprites["bldg_restaurant_a"]      = entry("buildings", comm_top[2], "building/restaurant", "clean", estimated=True)
    sprites["bldg_market_a"]          = entry("buildings", comm_top[3], "building/market",     "clean", estimated=True)

    # Bank + civic — individually detected as regions 11 and 12
    sprites["bldg_bank_a"]   = entry("buildings", r(11), "building/bank",  "clean")
    sprites["bldg_civic_a"]  = entry("buildings", r(12), "building/civic", "clean")

    # ── CIVIC COLUMNS  (civic_columns, 1 merged region with 2 buildings) ─────
    CC = S["civic_columns"]
    civic_pair = split_h(reg(CC, 0), 2)
    sprites["bldg_civic_columns_a"] = entry("civic_columns", civic_pair[0], "building/civic", "clean",    estimated=True)
    sprites["bldg_civic_columns_b"] = entry("civic_columns", civic_pair[1], "building/civic", "weathered",estimated=True)

    # ── LANDMARKS ─────────────────────────────────────────────────────────────
    LM = S["landmarks"]
    r = lambda i: reg(LM, i)

    # Town hall — row is merged into region [0]; split into 4 variants
    th_variants = split_h(r(0), 4)
    sprites["landmark_town_hall_a"]  = entry("landmarks", th_variants[0], "landmark/town_hall", "clean",    estimated=True)
    sprites["landmark_town_hall_b"]  = entry("landmarks", th_variants[1], "landmark/town_hall", "clean",    estimated=True)
    sprites["landmark_town_hall_c"]  = entry("landmarks", th_variants[2], "landmark/town_hall", "weathered",estimated=True)
    sprites["landmark_town_hall_d"]  = entry("landmarks", th_variants[3], "landmark/town_hall", "weathered",estimated=True)

    # Rows 2-5 are all merged into region [1]; split vertically into 4 rows then horizontally
    x1, y1, w1, h1 = r(1)
    row_h = h1 // 4
    for row_idx, (btype, slot) in enumerate([
        ("school",   "landmark/school"),
        ("hospital", "landmark/hospital"),
        ("police",   "landmark/police"),
        ("station",  "landmark/station"),
    ]):
        row_rect = [x1, y1 + row_idx * row_h, w1, row_h]
        variants = split_h(row_rect, 4)
        conds = ["clean", "clean", "weathered", "weathered"]
        for vi, (vr, cond) in enumerate(zip(variants, conds)):
            key = f"landmark_{btype}_{chr(ord('a') + vi)}"
            sprites[key] = entry("landmarks", vr, slot, cond, estimated=True)

    # Park monuments — individually detected as regions 2, 3, 4
    sprites["landmark_park_monument_a"] = entry("landmarks", r(2), "landmark/park_monument", "clean")
    sprites["landmark_park_monument_b"] = entry("landmarks", r(3), "landmark/park_monument", "clean")
    sprites["landmark_park_monument_c"] = entry("landmarks", r(4), "landmark/park_monument", "weathered")

    # ── COASTAL ───────────────────────────────────────────────────────────────
    # Coastal detection found 26 regions. Mapping based on visual layout:
    # sections: beach_edges(0-9), beach_corners(10-19), seawall(20-25), dock, cliff
    # NOTE: coastal detection is noisy (section labels detected as regions).
    # Assign by visual layout position from debug image.
    CO = S["coastal"]
    r = lambda i: reg(CO, i)

    # Beach edges — clean (region 1 = 3 tiles merged), weathered (region 5 = 3 tiles)
    beach_clean    = split_h(r(1),  3)
    beach_weathered= split_h(r(5),  3)
    for i, direction in enumerate(["n", "e", "s"]):
        sprites[f"coast_beach_{direction}"]           = entry("coastal", beach_clean[i],     "coast/beach", "clean",    estimated=True)
        sprites[f"coast_beach_{direction}_weathered"] = entry("coastal", beach_weathered[i], "coast/beach", "weathered",estimated=True)
    sprites["coast_beach_w"]           = entry("coastal", r(2),  "coast/beach", "clean")
    sprites["coast_beach_w_weathered"] = entry("coastal", r(6),  "coast/beach", "weathered")

    # Beach corners — region 3 = 4 corners merged
    beach_corners = split_h(r(3), 4)
    for i, corner in enumerate(["ne", "nw", "se", "sw"]):
        sprites[f"coast_beach_corner_{corner}"] = entry("coastal", beach_corners[i], "coast/beach", "clean", estimated=True)

    # Seawall edges — region 7 = 4 clean merged, region ?? weathered
    seawall_clean    = split_h(r(7), 4)
    seawall_weathered= split_h(r(8), 2)
    for i, direction in enumerate(["n", "e", "s", "w"]):
        sprites[f"coast_seawall_{direction}"]           = entry("coastal", seawall_clean[i], "coast/seawall", "clean",    estimated=True)
    for i, corner in enumerate(["ne", "nw"]):
        sprites[f"coast_seawall_corner_{corner}"]       = entry("coastal", seawall_weathered[i], "coast/seawall", "weathered", estimated=True)

    # Seawall corners — region 10
    sw_corners = split_h(r(10), 2)
    sprites["coast_seawall_corner_ne_clean"] = entry("coastal", sw_corners[0], "coast/seawall", "clean",    estimated=True)
    sprites["coast_seawall_corner_nw_clean"] = entry("coastal", sw_corners[1], "coast/seawall", "clean",    estimated=True)

    # Dock planks — regions 11,12 (ns clean, ew clean)
    sprites["coast_dock_plank_ns"]           = entry("coastal", r(11), "coast/dock", "clean")
    sprites["coast_dock_plank_ew"]           = entry("coastal", r(12), "coast/dock", "clean")
    sprites["coast_dock_plank_ns_weathered"] = entry("coastal", r(13), "coast/dock", "weathered")

    # Dock edges — regions 14,15 (n,e clean)
    sprites["coast_dock_edge_n"]           = entry("coastal", r(14), "coast/dock", "clean")
    sprites["coast_dock_edge_e"]           = entry("coastal", r(15), "coast/dock", "clean")
    sprites["coast_dock_edge_n_weathered"] = entry("coastal", r(17), "coast/dock", "weathered")
    sprites["coast_dock_edge_e_weathered"] = entry("coastal", r(18), "coast/dock", "weathered")

    # Cliff edges — regions 19-22 (n,e,s,w clean), 23,25 weathered
    cliff_dirs = ["n", "e", "s", "w"]
    for i, direction in enumerate(cliff_dirs):
        sprites[f"coast_cliff_{direction}"]           = entry("coastal", r(19 + i), "coast/cliff", "clean")
    sprites["coast_cliff_n_weathered"] = entry("coastal", r(23), "coast/cliff", "weathered")
    sprites["coast_cliff_e_weathered"] = entry("coastal", r(25), "coast/cliff", "weathered")

    # ── ROAD DIAGONALS ────────────────────────────────────────────────────────
    RD = S["road_diagonals"]
    r = lambda i: reg(RD, i)
    # Region [6] = road clean row merged, [10] = sidewalk block merged
    # Column headers are regions 0-5 (labels detected), actual tiles in row blocks
    road_diag_clean    = split_h(r(6),  6)
    road_diag_weathered= split_h(r(10), 6)
    diag_ids = ["road_diag_ne_sw", "road_diag_nw_se", "road_diag_t_ne",
                "road_diag_t_nw", "road_diag_x", "road_diag_sw_corner"]
    for i, did in enumerate(diag_ids):
        sprites[did]                = entry("road_diagonals", road_diag_clean[i],     "street/road",     "clean",    estimated=True)
        sprites[did + "_weathered"] = entry("road_diagonals", road_diag_weathered[i], "street/road",     "weathered",estimated=True)

    # Sidewalk diagonals — two separate blocks [7] NE-SW clean, [11] NW-SE clean
    sw_ne_sw_clean    = split_h(r(7),  5)
    sw_nw_se_clean    = split_h(r(11), 5)
    sw_ne_sw_weathered= split_h(r(12), 5)
    sprites["sw_diag_ne_sw"]           = entry("road_diagonals", sw_ne_sw_clean[0],    "street/sidewalk", "clean",    estimated=True)
    sprites["sw_diag_nw_se"]           = entry("road_diagonals", sw_nw_se_clean[0],    "street/sidewalk", "clean",    estimated=True)
    sprites["sw_diag_ne_sw_weathered"] = entry("road_diagonals", sw_ne_sw_weathered[0],"street/sidewalk", "weathered",estimated=True)
    sprites["sw_diag_nw_se_weathered"] = entry("road_diagonals", sw_ne_sw_weathered[1],"street/sidewalk", "weathered",estimated=True)

    # ── PARK OBJECTS ─────────────────────────────────────────────────────────
    PK = S["park_objects"]
    r = lambda i: reg(PK, i)
    sprites["park_tree_deciduous_a"]  = entry("park_objects", r(0),  "landscape/park", "clean")
    sprites["park_tree_deciduous_b"]  = entry("park_objects", r(1),  "landscape/park", "clean")
    sprites["park_tree_deciduous_c"]  = entry("park_objects", r(2),  "landscape/park", "clean")
    sprites["park_tree_evergreen_a"]  = entry("park_objects", r(3),  "landscape/park", "clean")  # merged pair, estimated
    sprites["park_tree_palm_a"]       = entry("park_objects", r(4),  "landscape/park", "clean")
    sprites["park_tree_palm_b"]       = entry("park_objects", r(5),  "landscape/park", "clean")
    sprites["park_bush_a"]            = entry("park_objects", r(6),  "landscape/park", "clean")
    sprites["park_bush_b"]            = entry("park_objects", r(7),  "landscape/park", "clean")
    sprites["park_bush_c"]            = entry("park_objects", r(8),  "landscape/park", "clean")
    sprites["park_bush_d"]            = entry("park_objects", r(9),  "landscape/park", "clean")
    sprites["park_bush_e"]            = entry("park_objects", r(10), "landscape/park", "clean")
    sprites["park_bush_f"]            = entry("park_objects", r(11), "landscape/park", "clean")
    sprites["park_bush_g"]            = entry("park_objects", r(12), "landscape/park", "clean")
    sprites["park_bench_a"]           = entry("park_objects", r(13), "prop/park",      "clean")
    sprites["park_bench_b"]           = entry("park_objects", r(14), "prop/park",      "clean")
    sprites["park_fountain_a"]        = entry("park_objects", r(15), "prop/park",      "clean")
    sprites["park_fountain_lg"]       = entry("park_objects", r(16), "prop/park",      "clean")
    sprites["park_path_ns"]           = entry("park_objects", r(17), "landscape/park", "clean")
    sprites["park_path_ew"]           = entry("park_objects", r(18), "landscape/park", "clean")
    # Path corners merged into large block r(19)
    path_corners = split_h(r(19), 4)
    for i, corner in enumerate(["ne", "nw", "se", "sw"]):
        sprites[f"park_path_corner_{corner}"] = entry("park_objects", path_corners[i], "landscape/park", "clean", estimated=True)
    sprites["park_bench_stone_a"]     = entry("park_objects", r(20), "prop/park",      "clean")
    sprites["park_bench_stone_b"]     = entry("park_objects", r(21), "prop/park",      "clean")
    sprites["park_wall_a"]            = entry("park_objects", r(22), "prop/park",      "clean")
    sprites["park_playground_a"]      = entry("park_objects", r(23), "prop/park",      "clean")
    sprites["park_playground_b"]      = entry("park_objects", r(24), "prop/park",      "clean")
    sprites["park_playground_c"]      = entry("park_objects", r(25), "prop/park",      "clean")
    sprites["park_wall_b"]            = entry("park_objects", r(26), "prop/park",      "clean")
    sprites["park_playground_d"]      = entry("park_objects", r(27), "prop/park",      "clean")
    sprites["park_playground_e"]      = entry("park_objects", r(28), "prop/park",      "clean")
    sprites["park_lamp_a"]            = entry("park_objects", r(29), "prop/park",      "clean")
    sprites["park_lamp_b"]            = entry("park_objects", r(30), "prop/park",      "clean")

    # ── ROOFS ─────────────────────────────────────────────────────────────────
    RO = S["roofs"]
    r = lambda i: reg(RO, i)
    # Region [0] = big block (entire top section merged), sub-regions 1-4 are corners
    roof_main = split_h(r(0), 4)
    sprites["roof_flat_a"]             = entry("roofs", roof_main[0], "building/roof", "clean",    estimated=True)
    sprites["roof_flat_b"]             = entry("roofs", roof_main[1], "building/roof", "clean",    estimated=True)
    sprites["roof_flat_a_corner"]      = entry("roofs", r(1),         "building/roof", "clean")
    sprites["roof_flat_b_corner"]      = entry("roofs", r(2),         "building/roof", "clean")
    # Mansard and terracotta rows are in [3] and [5]
    sprites["roof_mansard_a"]          = entry("roofs", r(3),         "building/roof", "clean",    city_profile="paris_haussmann")
    sprites["roof_mansard_a_corner"]   = entry("roofs", r(4),         "building/roof", "clean",    city_profile="paris_haussmann")
    row56 = split_v(r(5), 2)
    sprites["roof_terracotta_a"]       = entry("roofs", row56[0],     "building/roof", "clean",    city_profile="barcelona_eixample", estimated=True)
    sprites["roof_rowhouse_parapet"]   = entry("roofs", row56[1],     "building/roof", "clean",    city_profile="manhattan",           estimated=True)
    row6 = split_h(r(6), 3)
    sprites["roof_glass_tower"]        = entry("roofs", row6[0],      "building/roof", "clean",    estimated=True)
    sprites["roof_glass_tower_corner"] = entry("roofs", r(7),         "building/roof", "clean")
    sprites["roof_peaked_a"]           = entry("roofs", r(9),         "building/roof", "clean")
    sprites["roof_peaked_b"]           = entry("roofs", r(10),        "building/roof", "clean")

    # ── CITY-PROFILE KITS ─────────────────────────────────────────────────────
    KT = S["city_profile_kits"]
    r = lambda i: reg(KT, i)
    # 20 kit sprites, detected as 13 regions (some merged)
    # From visual layout: Manhattan top-left, Barcelona top-right, Paris middle, London bottom
    mhtn = split_v(r(0), 3)
    sprites["kit_mhtn_fire_escape_a"]    = entry("city_profile_kits", mhtn[0],  "prop/facade_kit", "clean", city_profile="manhattan")
    sprites["kit_mhtn_fire_escape_b"]    = entry("city_profile_kits", mhtn[1],  "prop/facade_kit", "clean", city_profile="manhattan")
    sprites["kit_mhtn_water_tower"]      = entry("city_profile_kits", mhtn[2],  "prop/facade_kit", "clean", city_profile="manhattan")
    sprites["kit_mhtn_brownstone_stoop"] = entry("city_profile_kits", r(1),     "prop/facade_kit", "clean", city_profile="manhattan")
    sprites["kit_mhtn_cornice_a"]        = entry("city_profile_kits", r(2),     "prop/facade_kit", "clean", city_profile="manhattan")

    bcn = split_v(r(3), 2)
    sprites["kit_bcn_balcony_a"]         = entry("city_profile_kits", bcn[0],   "prop/facade_kit", "clean", city_profile="barcelona_eixample")
    sprites["kit_bcn_balcony_b"]         = entry("city_profile_kits", bcn[1],   "prop/facade_kit", "clean", city_profile="barcelona_eixample")
    sprites["kit_bcn_chamfer_corner"]    = entry("city_profile_kits", r(5),     "prop/facade_kit", "clean", city_profile="barcelona_eixample")
    sprites["kit_bcn_awning_a"]          = entry("city_profile_kits", r(6),     "prop/facade_kit", "clean", city_profile="barcelona_eixample")
    sprites["kit_bcn_courtyard_gate"]    = entry("city_profile_kits", r(4),     "prop/facade_kit", "clean", city_profile="barcelona_eixample")

    paris = split_v(r(9), 3)
    sprites["kit_paris_balcony_ironwork"]= entry("city_profile_kits", paris[0], "prop/facade_kit", "clean", city_profile="paris_haussmann")
    sprites["kit_paris_mansard_dormer"]  = entry("city_profile_kits", paris[1], "prop/facade_kit", "clean", city_profile="paris_haussmann")
    sprites["kit_paris_storefront_boul"] = entry("city_profile_kits", r(7),     "prop/facade_kit", "clean", city_profile="paris_haussmann")
    sprites["kit_paris_lamp_post"]       = entry("city_profile_kits", r(8),     "prop/facade_kit", "clean", city_profile="paris_haussmann")
    sprites["kit_paris_arcade_pillar"]   = entry("city_profile_kits", paris[2], "prop/facade_kit", "clean", city_profile="paris_haussmann")

    sprites["kit_ldn_sash_window_a"]     = entry("city_profile_kits", r(10),    "prop/facade_kit", "clean", city_profile="london_organic")
    sprites["kit_ldn_bay_window_a"]      = entry("city_profile_kits", r(11),    "prop/facade_kit", "clean", city_profile="london_organic")
    sprites["kit_ldn_chimney_pot_a"]     = entry("city_profile_kits", r(12),    "prop/facade_kit", "clean", city_profile="london_organic")
    sprites["kit_ldn_shopfront_a"]       = entry("city_profile_kits", r(4),     "prop/facade_kit", "clean", city_profile="london_organic")
    sprites["kit_ldn_fanlight_door"]     = entry("city_profile_kits", r(4),     "prop/facade_kit", "clean", city_profile="london_organic")

    # ── STREET PROPS ──────────────────────────────────────────────────────────
    SP = S["street_props"]
    r = lambda i: reg(SP, i)
    # Row 1: traffic lights (0-4 are variants), row 2: signs+shelters, rows 3-7: booths/hydrants/atms/newspapers
    sprites["prop_traffic_light_ns"]    = entry("street_props", r(0),  "prop/street", "clean")
    sprites["prop_traffic_light_ew"]    = entry("street_props", r(3),  "prop/street", "clean")
    sprites["prop_traffic_light_ns_w"]  = entry("street_props", r(4),  "prop/street", "weathered")
    sprites["prop_traffic_light_arm"]   = entry("street_props", r(5),  "prop/street", "clean")
    sprites["prop_traffic_light_arm_b"] = entry("street_props", r(6),  "prop/street", "clean")
    sprites["prop_traffic_light_arm_w"] = entry("street_props", r(7),  "prop/street", "weathered")
    sprites["prop_traffic_light_arm_c"] = entry("street_props", r(8),  "prop/street", "weathered")
    sprites["prop_street_sign_post"]    = entry("street_props", r(9),  "prop/street", "clean")
    sprites["prop_street_sign_cross"]   = entry("street_props", r(10), "prop/street", "clean")
    sprites["prop_bus_stop_a"]          = entry("street_props", r(11), "prop/street", "clean")
    # Phone booth variants
    sprites["prop_phone_booth_a"]       = entry("street_props", r(12), "prop/street", "clean")
    sprites["prop_phone_booth_b"]       = entry("street_props", r(13), "prop/street", "clean")
    sprites["prop_news_box_a"]          = entry("street_props", r(14), "prop/street", "clean")
    sprites["prop_phone_booth_c"]       = entry("street_props", r(15), "prop/street", "clean")
    sprites["prop_phone_booth_d"]       = entry("street_props", r(16), "prop/street", "weathered")
    sprites["prop_phone_booth_e"]       = entry("street_props", r(17), "prop/street", "weathered")
    sprites["prop_phone_booth_f"]       = entry("street_props", r(18), "prop/street", "weathered")
    sprites["prop_phone_booth_g"]       = entry("street_props", r(19), "prop/street", "weathered")
    # Hydrant variants
    sprites["prop_hydrant_a"]           = entry("street_props", r(20), "prop/street", "clean")
    sprites["prop_hydrant_b"]           = entry("street_props", r(21), "prop/street", "clean")
    sprites["prop_hydrant_c"]           = entry("street_props", r(22), "prop/street", "weathered")
    sprites["prop_hydrant_d"]           = entry("street_props", r(23), "prop/street", "weathered")
    sprites["prop_hydrant_e"]           = entry("street_props", r(24), "prop/street", "weathered")
    sprites["prop_newspaper_pile"]      = entry("street_props", r(25), "prop/street", "clean")
    sprites["prop_newspaper_pile_b"]    = entry("street_props", r(26), "prop/street", "weathered")
    sprites["prop_atm_a"]               = entry("street_props", r(27), "prop/street", "clean")
    sprites["prop_atm_b"]               = entry("street_props", r(28), "prop/street", "clean")
    sprites["prop_atm_c"]               = entry("street_props", r(29), "prop/street", "weathered")

    # ── NIGHT OVERLAYS ────────────────────────────────────────────────────────
    NO = S["night_overlays"]
    r = lambda i: reg(NO, i)
    # 5 overlay types x multiple intensity rows
    sprites["overlay_window_lit_warm"]   = entry("night_overlays", r(0),  "overlay/lighting", "clean")
    sprites["overlay_window_lit_warm_b"] = entry("night_overlays", r(8),  "overlay/lighting", "clean")
    sprites["overlay_window_lit_warm_c"] = entry("night_overlays", r(11), "overlay/lighting", "clean")
    sprites["overlay_window_lit_warm_d"] = entry("night_overlays", r(15), "overlay/lighting", "clean")
    sprites["overlay_window_lit_cold"]   = entry("night_overlays", r(3),  "overlay/lighting", "clean")
    sprites["overlay_window_lit_cold_b"] = entry("night_overlays", r(9),  "overlay/lighting", "clean")
    sprites["overlay_window_lit_cold_c"] = entry("night_overlays", r(12), "overlay/lighting", "clean")
    sprites["overlay_window_lit_cold_d"] = entry("night_overlays", r(16), "overlay/lighting", "clean")
    sprites["overlay_lamp_cone_a"]       = entry("night_overlays", r(5),  "overlay/lighting", "clean")
    sprites["overlay_lamp_cone_b"]       = entry("night_overlays", r(13), "overlay/lighting", "clean")
    sprites["overlay_lamp_cone_c"]       = entry("night_overlays", r(17), "overlay/lighting", "clean")
    sprites["overlay_sign_neon_a"]       = entry("night_overlays", r(6),  "overlay/lighting", "clean")
    sprites["overlay_sign_neon_b"]       = entry("night_overlays", r(7),  "overlay/lighting", "clean")
    sprites["overlay_sign_neon_c"]       = entry("night_overlays", r(14), "overlay/lighting", "clean")
    sprites["overlay_sign_neon_d"]       = entry("night_overlays", r(18), "overlay/lighting", "clean")

    # ── BUILDING OVERLAYS ─────────────────────────────────────────────────────
    BO = S["building_overlays"]
    r = lambda i: reg(BO, i)
    sprites["shadow_bldg_2x2"]           = entry("building_overlays", r(0), "overlay/shadow",     "clean")
    sprites["shadow_bldg_2x1"]           = entry("building_overlays", r(1), "overlay/shadow",     "clean")
    sprites["shadow_bldg_1x1"]           = entry("building_overlays", r(2), "overlay/shadow",     "clean")
    sprites["overlay_bldg_graffiti_a"]   = entry("building_overlays", r(7), "overlay/weathering", "weathered")
    sprites["overlay_bldg_graffiti_b"]   = entry("building_overlays", r(3), "overlay/weathering", "weathered")
    sprites["overlay_bldg_stain_a"]      = entry("building_overlays", r(4), "overlay/weathering", "weathered")
    sprites["overlay_bldg_moss_a"]       = entry("building_overlays", r(5), "overlay/weathering", "weathered")
    sprites["overlay_bldg_damage_a"]     = entry("building_overlays", r(6), "overlay/weathering", "weathered")

    return sprites


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    with open(DETECTED_JSON, encoding="utf-8") as f:
        detected = json.load(f)

    sprites = build_registry(detected)

    registry = {
        "schema": "sprite_registry.v1",
        "status": "source_detected_partial_mapping",
        "pipeline_note": (
            "All source sheets are RGB (no alpha). Every sprite requires alpha "
            "conversion before runtime use. pixel_rects marked 'estimated: true' "
            "are computed by equal-splitting merged regions and need manual "
            "verification when slicing."
        ),
        "total_sprites": len(sprites),
        "sprites": sprites,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(f"Wrote {len(sprites)} sprite entries -> {OUT_JSON}")

    # Quick summary by asset_slot
    from collections import Counter
    slot_counts = Counter(v["asset_slot"] for v in sprites.values())
    print("\nBy asset_slot:")
    for slot, count in sorted(slot_counts.items()):
        print(f"  {slot:<30} {count}")

    estimated = sum(1 for v in sprites.values() if v.get("estimated"))
    print(f"\n{estimated} entries have estimated rects (need manual verification)")


if __name__ == "__main__":
    main()
