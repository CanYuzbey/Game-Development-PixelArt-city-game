#!/usr/bin/env python3
"""
Finalize sprite sheets after alpha conversion and automated detection.

This pass handles the parts that need visual judgment:
  - remove printed source-sheet labels that became opaque during alpha cleanup
  - replace mechanically split rects with visually isolated sprite rects
  - trim transparent padding after labels are removed
  - clear all remaining "estimated" flags

The script intentionally avoids scipy so it can run on the bundled Codex Python.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RGBA_DIR = ROOT / "assets" / "source_rgba"
MANIFEST_DIR = ROOT / "assets" / "manifests"
REGISTRY_PATH = MANIFEST_DIR / "sprite_registry.json"

LABEL_SHEETS = {
    "buildings",
    "city_profile_kits",
    "coastal",
    "night_overlays",
    "road_diagonals",
}


def connected_components(mask: np.ndarray):
    """Yield (x, y, w, h, points) components for a small number of alpha blobs."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    ys, xs = np.where(mask)

    for start_y, start_x in zip(ys, xs):
        if seen[start_y, start_x]:
            continue

        stack = [(int(start_y), int(start_x))]
        seen[start_y, start_x] = True
        points = []
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)

        while stack:
            y, x = stack.pop()
            points.append((y, x))
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if (
                        ny < 0
                        or nx < 0
                        or ny >= height
                        or nx >= width
                        or seen[ny, nx]
                        or not mask[ny, nx]
                    ):
                        continue
                    seen[ny, nx] = True
                    stack.append((ny, nx))

        yield min_x, min_y, max_x - min_x + 1, max_y - min_y + 1, points


def is_source_label_component(arr: np.ndarray, x: int, y: int, w: int, h: int, points) -> bool:
    """Detect label-word blobs, which are short opaque checker/text rectangles."""
    area = len(points)
    if not (35 <= w <= 280 and 15 <= h <= 30 and 500 <= area <= 6000):
        return False

    density = area / float(w * h)
    if density < 0.55:
        return False

    pixels = np.array([arr[py, px, :3] for py, px in points], dtype=np.float32)
    brightness = float(pixels.mean())
    return brightness >= 130.0


def strip_source_labels() -> dict[str, int]:
    removed: dict[str, int] = {}

    for sheet_id in sorted(LABEL_SHEETS):
        path = RGBA_DIR / f"{sheet_id}.png"
        if not path.exists():
            continue

        img = Image.open(path).convert("RGBA")
        arr = np.array(img)
        alpha = arr[:, :, 3] > 0

        label_points = []
        for x, y, w, h, points in connected_components(alpha):
            if is_source_label_component(arr, x, y, w, h, points):
                label_points.extend(points)

        for y, x in label_points:
            arr[y, x, 3] = 0

        if label_points:
            Image.fromarray(arr, mode="RGBA").save(path)

        removed[sheet_id] = len(label_points)

    return removed


def rect(x: int, y: int, w: int, h: int) -> list[int]:
    return [x, y, w, h]


def pad_rect(x: int, y: int, w: int, h: int, pad: int = 4) -> list[int]:
    return [max(0, x - pad), max(0, y - pad), w + pad * 2, h + pad * 2]


RECT_OVERRIDES = {
    # Buildings sheet. The detector saw some printed labels as regions, so this
    # map uses the visible building bodies directly.
    "bldg_cbd_glass_a": pad_rect(31, 25, 107, 206),
    "bldg_cbd_glass_b": pad_rect(273, 33, 101, 195),
    "bldg_cbd_brick_a": pad_rect(512, 24, 112, 209),
    "bldg_cbd_concrete_a": pad_rect(766, 24, 105, 207),
    "bldg_cbd_corner_glass": pad_rect(1008, 34, 98, 200),
    "bldg_mid_brownstone_a": pad_rect(21, 284, 98, 194),
    "bldg_mid_brownstone_b": pad_rect(128, 285, 96, 194),
    "bldg_mid_brick_a": pad_rect(477, 300, 169, 178),
    "bldg_mid_brick_b": pad_rect(665, 301, 174, 180),
    "bldg_mid_stucco_a": pad_rect(863, 300, 173, 182),
    "bldg_mid_limestone_a": pad_rect(1059, 303, 176, 182),
    "bldg_resi_rowhouse_a": pad_rect(17, 547, 109, 179),
    "bldg_resi_rowhouse_b": pad_rect(128, 553, 107, 175),
    "bldg_resi_terrace_a": pad_rect(496, 547, 183, 191),
    "bldg_resi_detached_a": pad_rect(706, 550, 260, 181),
    "bldg_resi_detached_b": pad_rect(971, 554, 264, 182),
    "bldg_shop_storefront_a": pad_rect(31, 802, 119, 147),
    "bldg_shop_storefront_b": rect(288, 792, 227, 160),
    "bldg_restaurant_a": rect(575, 789, 169, 160),
    "bldg_market_a": rect(905, 791, 214, 160),
    "bldg_bank_a": rect(55, 996, 135, 190),
    "bldg_civic_a": pad_rect(420, 1002, 202, 207),

    # Civic sheet: two large civic buildings previously came from one merged region.
    "bldg_civic_columns_a": pad_rect(41, 336, 572, 560),
    "bldg_civic_columns_b": pad_rect(621, 338, 572, 558),

    # Coastal beach edges and corners.
    "coast_beach_n": pad_rect(128, 60, 130, 81),
    "coast_beach_e": pad_rect(273, 60, 117, 82),
    "coast_beach_s": pad_rect(410, 61, 121, 80),
    "coast_beach_w": pad_rect(553, 62, 66, 79),
    "coast_beach_n_weathered": pad_rect(128, 164, 130, 82),
    "coast_beach_e_weathered": pad_rect(273, 164, 117, 82),
    "coast_beach_s_weathered": pad_rect(410, 166, 120, 80),
    "coast_beach_w_weathered": pad_rect(552, 166, 67, 80),
    "coast_beach_corner_ne": pad_rect(681, 51, 135, 101),
    "coast_beach_corner_nw": pad_rect(828, 53, 132, 99),
    "coast_beach_corner_se": pad_rect(970, 55, 127, 96),
    "coast_beach_corner_sw": pad_rect(1106, 54, 126, 96),

    # Coastal seawalls. Clean edge ids use the clean row; corner ids keep the
    # registry's existing clean/weathered naming.
    "coast_seawall_n": pad_rect(124, 323, 135, 96),
    "coast_seawall_e": pad_rect(273, 323, 121, 96),
    "coast_seawall_s": pad_rect(411, 322, 130, 97),
    "coast_seawall_w": pad_rect(555, 322, 75, 97),
    "coast_seawall_corner_ne_clean": rect(672, 316, 164, 112),
    "coast_seawall_corner_nw_clean": pad_rect(844, 316, 111, 110),
    "coast_seawall_corner_ne": pad_rect(676, 428, 154, 111),
    "coast_seawall_corner_nw": pad_rect(844, 432, 111, 111),

    # Docks and cliffs.
    "coast_dock_plank_ns": pad_rect(128, 595, 107, 89),
    "coast_dock_plank_ew": pad_rect(257, 594, 120, 89),
    "coast_dock_plank_ns_weathered": pad_rect(128, 697, 107, 91),
    "coast_dock_edge_n": pad_rect(413, 591, 216, 89),
    "coast_dock_edge_e": pad_rect(672, 602, 182, 80),
    "coast_dock_edge_n_weathered": pad_rect(413, 695, 216, 90),
    "coast_dock_edge_e_weathered": pad_rect(672, 707, 183, 81),
    "coast_cliff_n": pad_rect(125, 846, 181, 89),
    "coast_cliff_e": pad_rect(333, 845, 160, 90),
    "coast_cliff_s": pad_rect(550, 847, 181, 88),
    "coast_cliff_w": pad_rect(774, 847, 186, 88),
    "coast_cliff_n_weathered": pad_rect(125, 954, 181, 91),
    "coast_cliff_e_weathered": pad_rect(333, 953, 160, 92),

    # Road diagonal sheet: remove label components as sprites and point ids at
    # the actual clean/weathered road and sidewalk tiles.
    "road_diag_ne_sw": pad_rect(142, 108, 170, 175),
    "road_diag_nw_se": pad_rect(327, 108, 169, 175),
    "road_diag_t_ne": pad_rect(512, 106, 168, 181),
    "road_diag_t_nw": pad_rect(693, 106, 170, 181),
    "road_diag_x": pad_rect(881, 106, 171, 176),
    "road_diag_sw_corner": pad_rect(1073, 108, 167, 179),
    "road_diag_ne_sw_weathered": pad_rect(142, 299, 169, 175),
    "road_diag_nw_se_weathered": pad_rect(327, 299, 169, 176),
    "road_diag_t_ne_weathered": pad_rect(512, 298, 168, 181),
    "road_diag_t_nw_weathered": pad_rect(693, 298, 170, 182),
    "road_diag_x_weathered": pad_rect(881, 298, 171, 176),
    "road_diag_sw_corner_weathered": pad_rect(1073, 300, 168, 178),
    "sw_diag_ne_sw": pad_rect(142, 506, 169, 172),
    "sw_diag_nw_se": pad_rect(142, 691, 169, 175),
    "sw_diag_ne_sw_weathered": pad_rect(142, 867, 169, 174),
    "sw_diag_nw_se_weathered": pad_rect(142, 1052, 168, 175),

    # Park objects: several detector regions covered two props or whole rows.
    "park_tree_deciduous_a": pad_rect(61, 43, 126, 198),
    "park_tree_deciduous_b": pad_rect(236, 46, 136, 195),
    "park_tree_deciduous_c": pad_rect(401, 50, 121, 191),
    "park_tree_evergreen_a": pad_rect(623, 35, 119, 211),
    "park_tree_palm_a": pad_rect(944, 35, 113, 211),
    "park_tree_palm_b": pad_rect(1094, 35, 117, 211),
    "park_bush_a": pad_rect(70, 275, 116, 111),
    "park_bush_b": pad_rect(238, 280, 116, 106),
    "park_bush_c": pad_rect(403, 277, 112, 109),
    "park_bush_d": pad_rect(585, 289, 141, 105),
    "park_bush_e": pad_rect(769, 278, 135, 116),
    "park_bush_f": pad_rect(943, 282, 117, 109),
    "park_bush_g": pad_rect(1097, 279, 112, 112),
    "park_bench_a": pad_rect(69, 418, 157, 139),
    "park_bench_b": pad_rect(353, 420, 156, 137),
    "park_fountain_a": pad_rect(81, 582, 164, 148),
    "park_fountain_lg": pad_rect(594, 546, 253, 198),
    "park_path_ns": pad_rect(83, 767, 98, 200),
    "park_path_ew": pad_rect(348, 776, 262, 81),
    "park_path_corner_ne": pad_rect(646, 778, 121, 108),
    "park_path_corner_nw": pad_rect(788, 784, 100, 90),
    "park_path_corner_se": pad_rect(940, 783, 89, 90),
    "park_path_corner_sw": pad_rect(1087, 783, 91, 90),
    "park_bench_stone_a": pad_rect(628, 429, 247, 116),
    "park_bench_stone_b": pad_rect(940, 427, 251, 120),
    "park_wall_a": pad_rect(207, 767, 98, 201),
    "park_wall_b": pad_rect(348, 881, 262, 81),
    "park_playground_a": pad_rect(51, 1018, 158, 172),
    "park_playground_b": pad_rect(236, 1019, 155, 171),
    "park_playground_c": pad_rect(407, 990, 191, 216),
    "park_playground_d": pad_rect(612, 995, 194, 215),
    "park_playground_e": pad_rect(646, 892, 118, 101),
    "park_lamp_a": pad_rect(872, 1015, 47, 185),
    "park_lamp_b": pad_rect(1036, 1016, 47, 184),

    # City-profile facade kits.
    "kit_mhtn_fire_escape_a": pad_rect(35, 44, 178, 257),
    "kit_mhtn_fire_escape_b": pad_rect(276, 38, 167, 261),
    "kit_mhtn_water_tower": pad_rect(541, 42, 155, 264),
    "kit_mhtn_brownstone_stoop": pad_rect(766, 26, 197, 280),
    "kit_mhtn_cornice_a": rect(1010, 91, 220, 210),
    "kit_bcn_balcony_a": rect(30, 344, 187, 260),
    "kit_bcn_balcony_b": rect(272, 340, 164, 267),
    "kit_bcn_chamfer_corner": pad_rect(520, 379, 174, 224),
    "kit_bcn_awning_a": pad_rect(746, 412, 223, 182),
    "kit_bcn_courtyard_gate": rect(1010, 344, 193, 260),
    "kit_paris_balcony_ironwork": pad_rect(26, 660, 197, 228),
    "kit_paris_mansard_dormer": rect(258, 674, 218, 210),
    "kit_paris_storefront_boul": rect(499, 653, 235, 230),
    "kit_paris_lamp_post": rect(779, 649, 168, 230),
    "kit_paris_arcade_pillar": rect(1013, 650, 188, 234),
    "kit_ldn_sash_window_a": rect(47, 931, 144, 255),
    "kit_ldn_bay_window_a": rect(286, 926, 168, 257),
    "kit_ldn_chimney_pot_a": rect(520, 945, 181, 241),
    "kit_ldn_shopfront_a": rect(752, 933, 213, 251),
    "kit_ldn_fanlight_door": rect(1020, 926, 175, 258),
}


def trim_to_alpha(sheet_cache: dict[str, np.ndarray], sheet_id: str, pixel_rect: list[int]) -> list[int]:
    arr = sheet_cache[sheet_id]
    sheet_h, sheet_w = arr.shape[:2]
    x, y, w, h = pixel_rect
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(sheet_w, x + w)
    y1 = min(sheet_h, y + h)
    if x1 <= x0 or y1 <= y0:
        return pixel_rect

    crop_alpha = arr[y0:y1, x0:x1, 3]
    ys, xs = np.where(crop_alpha > 0)
    if len(xs) == 0:
        return pixel_rect

    pad = 4
    nx0 = max(0, x0 + int(xs.min()) - pad)
    ny0 = max(0, y0 + int(ys.min()) - pad)
    nx1 = min(sheet_w, x0 + int(xs.max()) + 1 + pad)
    ny1 = min(sheet_h, y0 + int(ys.max()) + 1 + pad)
    return [nx0, ny0, nx1 - nx0, ny1 - ny0]


def finalize_registry() -> tuple[int, int]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry = json.load(f)

    sprites = registry["sprites"]
    sheet_ids = {info["source_sheet"] for info in sprites.values()}
    sheet_cache = {
        sheet_id: np.array(Image.open(RGBA_DIR / f"{sheet_id}.png").convert("RGBA"))
        for sheet_id in sheet_ids
    }

    overrides_applied = 0
    for sprite_id, pixel_rect in RECT_OVERRIDES.items():
        if sprite_id not in sprites:
            continue
        sprites[sprite_id]["pixel_rect"] = pixel_rect
        sprites[sprite_id].pop("estimated", None)
        sprites[sprite_id]["visual_rect"] = "curated"
        overrides_applied += 1

    for sprite_id, info in sprites.items():
        info["pixel_rect"] = trim_to_alpha(sheet_cache, info["source_sheet"], info["pixel_rect"])
        info.pop("estimated", None)
        if sprite_id not in RECT_OVERRIDES:
            info["visual_rect"] = "alpha_trimmed"

    registry["status"] = "visual_finalized"
    registry["pipeline_note"] = (
        "Visual finalization removed printed source labels, replaced merged or "
        "mechanically split rects with curated sprite rects, trimmed transparent "
        "padding, and cleared all estimated flags."
    )
    registry["total_sprites"] = len(sprites)

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    estimated_left = sum(1 for info in sprites.values() if info.get("estimated"))
    return overrides_applied, estimated_left


def main() -> None:
    removed = strip_source_labels()
    overrides_applied, estimated_left = finalize_registry()

    print("=== Visual Asset Finalizer ===")
    print("Label pixels removed:")
    for sheet_id, count in sorted(removed.items()):
        print(f"  {sheet_id:20s} {count:6d}")
    print(f"Curated rect overrides: {overrides_applied}")
    print(f"Estimated flags left: {estimated_left}")
    print(f"Updated {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
