#!/usr/bin/env python3
"""
tools/calibrate_rects.py
========================
Re-detects bounding boxes for 5 sprite sheets where dilation=12 merged
nearby sprites into row-level blobs.  Uses DILATION_ITERS=4 for those
sheets only, keeps all other detection parameters identical.

Outputs:
  assets/debug/{sheet_id}_v2_debug.png   -- coloured numbered debug overlays
  assets/manifests/detected_regions_v2.json -- new per-sheet regions (5 sheets
                                               replaced, 7 sheets kept as-is)
  assets/manifests/sprite_registry.json  -- estimated: true sprites upgraded
                                            with exact pixel_rects where possible

Usage:
    python tools/calibrate_rects.py
"""

import json
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR   = os.path.join(ROOT, "assets", "source")
DEBUG_DIR    = os.path.join(ROOT, "assets", "debug")
MANIFEST_DIR = os.path.join(ROOT, "assets", "manifests")

ORIG_MANIFEST   = os.path.join(MANIFEST_DIR, "detected_regions.json")
V2_MANIFEST     = os.path.join(MANIFEST_DIR, "detected_regions_v2.json")
REGISTRY_PATH   = os.path.join(MANIFEST_DIR, "sprite_registry.json")

# ── Detection parameters ───────────────────────────────────────────────────────
BG_THRESHOLD   = 170
MIN_AREA       = 1500
DILATION_ITERS = 4    # reduced from 12
BOX_PADDING    = 6

# ── Sheets to re-detect ────────────────────────────────────────────────────────
REDETECT_SHEETS = {
    "buildings":         "Buildings (CBD / mid-rise / residential / commercial)",
    "landmarks":         "Landmark buildings",
    "roofs":             "Roof variants",
    "city_profile_kits": "City-profile facade kits",
    "road_diagonals":    "Diagonal road & sidewalk tiles",
}

EXPECTED_COUNTS = {
    "buildings":         22,
    "landmarks":         24,
    "roofs":             16,
    "city_profile_kits": 20,
    "road_diagonals":    14,
}

# ── Sprite-ID mappings (detection order: top-to-bottom, left-to-right) ────────
SPRITE_ID_MAPS = {
    "buildings": [
        # Row 1 (CBD)
        "bldg_cbd_glass_a", "bldg_cbd_glass_b", "bldg_cbd_brick_a",
        "bldg_cbd_concrete_a", "bldg_cbd_corner_glass",
        # Row 2 (mid)
        "bldg_mid_brownstone_a", "bldg_mid_brownstone_b", "bldg_mid_brick_a",
        "bldg_mid_brick_b", "bldg_mid_stucco_a", "bldg_mid_limestone_a",
        # Row 3 (resi)
        "bldg_resi_rowhouse_a", "bldg_resi_rowhouse_b", "bldg_resi_terrace_a",
        "bldg_resi_detached_a", "bldg_resi_detached_b",
        # Row 4 (comm)
        "bldg_shop_storefront_a", "bldg_shop_storefront_b",
        "bldg_restaurant_a", "bldg_market_a",
        # Row 5 (civic)
        "bldg_bank_a", "bldg_civic_a",
    ],
    "landmarks": [
        # Row 1 (town_hall)
        "landmark_town_hall_a", "landmark_town_hall_b",
        "landmark_town_hall_c", "landmark_town_hall_d",
        # Row 2 (school)
        "landmark_school_a", "landmark_school_b",
        "landmark_school_c", "landmark_school_d",
        # Row 3 (hospital)
        "landmark_hospital_a", "landmark_hospital_b",
        "landmark_hospital_c", "landmark_hospital_d",
        # Row 4 (police)
        "landmark_police_a", "landmark_police_b",
        "landmark_police_c", "landmark_police_d",
        # Row 5 (station)
        "landmark_station_a", "landmark_station_b",
        "landmark_station_c", "landmark_station_d",
        # Row 6 (monument)
        "landmark_park_monument_a", "landmark_park_monument_b",
        "landmark_park_monument_c",
        "landmark_park_monument_d", "landmark_park_monument_e",
        "landmark_park_monument_f", "landmark_park_monument_g",
        "landmark_park_monument_h",
    ],
    "roofs": [
        "roof_flat_a", "roof_flat_a_corner",
        "roof_flat_b", "roof_flat_b_corner",
        "roof_mansard_a", "roof_mansard_a_corner",
        "roof_terracotta_a", "roof_terracotta_a_corner",
        "roof_glass_tower", "roof_glass_tower_corner",
        "roof_rowhouse_parapet", "roof_rowhouse_parapet_corner",
        "roof_peaked_a", "roof_peaked_a_corner",
        "roof_peaked_b", "roof_peaked_b_corner",
    ],
    "city_profile_kits": [
        "kit_mhtn_fire_escape_a", "kit_mhtn_fire_escape_b",
        "kit_mhtn_water_tower", "kit_mhtn_brownstone_stoop",
        "kit_mhtn_cornice_a",
        "kit_bcn_balcony_a", "kit_bcn_balcony_b",
        "kit_bcn_chamfer_corner", "kit_bcn_awning_a",
        "kit_bcn_courtyard_gate",
        "kit_paris_balcony_ironwork", "kit_paris_mansard_dormer",
        "kit_paris_storefront_boul", "kit_paris_lamp_post",
        "kit_paris_arcade_pillar",
        "kit_ldn_sash_window_a", "kit_ldn_bay_window_a",
        "kit_ldn_chimney_pot_a", "kit_ldn_shopfront_a",
        "kit_ldn_fanlight_door",
    ],
    "road_diagonals": [
        "road_diag_ne_sw", "road_diag_nw_se", "road_diag_t_ne",
        "road_diag_t_nw", "road_diag_x", "road_diag_sw_corner",
        "road_diag_ne_sw_weathered", "road_diag_nw_se_weathered",
        "road_diag_t_ne_weathered", "road_diag_t_nw_weathered",
        "road_diag_x_weathered", "road_diag_sw_corner_weathered",
        "sw_diag_ne_sw", "sw_diag_nw_se",
        "sw_diag_ne_sw_weathered", "sw_diag_nw_se_weathered",
    ],
}

# ── Debug colour palette ───────────────────────────────────────────────────────
PALETTE = [
    "#E63946", "#F4A261", "#2A9D8F", "#457B9D", "#E9C46A",
    "#A8DADC", "#6A4C93", "#F72585", "#4CC9F0", "#80B918",
]


# ── Core detection helpers ─────────────────────────────────────────────────────

def detect_bg_threshold(arr: np.ndarray) -> int:
    h, w = arr.shape[:2]
    margin = min(30, h // 10, w // 10)
    corners = np.concatenate([
        arr[:margin, :margin].reshape(-1, 3),
        arr[:margin, w - margin:].reshape(-1, 3),
        arr[h - margin:, :margin].reshape(-1, 3),
        arr[h - margin:, w - margin:].reshape(-1, 3),
    ])
    min_channels = corners.min(axis=1)
    threshold = int(np.percentile(min_channels, 10)) - 10
    return max(threshold, 140)


def find_sprite_bboxes(img_path: str, dilation_iters: int = DILATION_ITERS):
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    threshold = detect_bg_threshold(arr)

    is_fg = (arr[:, :, 0] < threshold) | \
            (arr[:, :, 1] < threshold) | \
            (arr[:, :, 2] < threshold)

    struct = ndimage.generate_binary_structure(2, 2)
    dilated = ndimage.binary_dilation(is_fg, structure=struct,
                                      iterations=dilation_iters)

    labeled, num_features = ndimage.label(dilated)

    bboxes = []
    for region_id in range(1, num_features + 1):
        ys, xs = np.where(labeled == region_id)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        area = (x_max - x_min) * (y_max - y_min)
        if area < MIN_AREA:
            continue
        x0 = max(0, x_min - BOX_PADDING)
        y0 = max(0, y_min - BOX_PADDING)
        x1 = min(w - 1, x_max + BOX_PADDING)
        y1 = min(h - 1, y_max + BOX_PADDING)
        bboxes.append((x0, y0, x1 - x0, y1 - y0))

    bboxes.sort(key=lambda b: (b[1] // 60, b[0]))
    return bboxes


def generate_debug_image(source_path: str, debug_path: str,
                         bboxes: list) -> None:
    img = Image.open(source_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    for idx, (x, y, bw, bh) in enumerate(bboxes):
        colour = PALETTE[idx % len(PALETTE)]
        draw.rectangle([x, y, x + bw, y + bh], outline=colour, width=2)
        label = str(idx)
        draw.text((x + 3, y + 3), label, fill=(0, 0, 0, 200))
        draw.text((x + 2, y + 2), label, fill=(255, 255, 255, 255))
    img.save(debug_path)
    print(f"  debug -> {os.path.basename(debug_path)}  ({len(bboxes)} regions)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)

    # ── 1. Load original manifest ──────────────────────────────────────────────
    with open(ORIG_MANIFEST, encoding="utf-8") as f:
        orig = json.load(f)

    v2 = {"schema": "detected_regions.v2", "sheets": {}}

    # Copy unchanged sheets verbatim
    for sheet_id, data in orig["sheets"].items():
        if sheet_id not in REDETECT_SHEETS:
            v2["sheets"][sheet_id] = data

    # ── 2. Re-detect the 5 sheets ──────────────────────────────────────────────
    new_regions: dict[str, list] = {}   # sheet_id -> list of (x,y,w,h)
    old_counts:  dict[str, int]  = {}

    print("\n=== Re-detecting 5 sheets with DILATION_ITERS=4 ===\n")

    for sheet_id, description in REDETECT_SHEETS.items():
        src = os.path.join(SOURCE_DIR, f"{sheet_id}.png")
        if not os.path.exists(src):
            print(f"[SKIP] {sheet_id}.png not found")
            # Keep original
            if sheet_id in orig["sheets"]:
                v2["sheets"][sheet_id] = orig["sheets"][sheet_id]
            continue

        img = Image.open(src)
        old_count = orig["sheets"].get(sheet_id, {}).get("detected_region_count", "?")
        old_counts[sheet_id] = old_count
        print(f"[{sheet_id}]  {img.size[0]}x{img.size[1]}  (was {old_count} regions)")

        bboxes = find_sprite_bboxes(src, dilation_iters=DILATION_ITERS)
        new_regions[sheet_id] = bboxes

        debug_path = os.path.join(DEBUG_DIR, f"{sheet_id}_v2_debug.png")
        generate_debug_image(src, debug_path, bboxes)

        v2["sheets"][sheet_id] = {
            "description": description,
            "source_file": f"source/{sheet_id}.png",
            "size": list(img.size),
            "mode": img.mode,
            "alpha_status": "RGB_no_alpha_needs_conversion",
            "dilation_iters": DILATION_ITERS,
            "detected_region_count": len(bboxes),
            "regions": [
                {"index": i, "pixel_rect": list(bb)}
                for i, bb in enumerate(bboxes)
            ],
        }

    # ── 3. Write detected_regions_v2.json ─────────────────────────────────────
    with open(V2_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(v2, f, indent=2)
    print(f"\nWrote {V2_MANIFEST}")

    # ── 4. Update sprite_registry.json ────────────────────────────────────────
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry = json.load(f)

    sprites = registry["sprites"]
    total_upgraded = 0

    print("\n=== Updating sprite_registry.json ===\n")

    for sheet_id, bboxes in new_regions.items():
        id_list     = SPRITE_ID_MAPS.get(sheet_id, [])
        expected    = EXPECTED_COUNTS.get(sheet_id, 0)
        old_count   = old_counts.get(sheet_id, "?")
        new_count   = len(bboxes)

        print(f"[{sheet_id}]  {old_count} -> {new_count} regions  "
              f"(expected ~{expected}, id_list len={len(id_list)})")

        if new_count < expected:
            print(f"  WARNING: only {new_count} regions detected, "
                  f"expected ~{expected}. Skipping registry update for this sheet.")
            continue

        upgraded = 0
        for i, sprite_id in enumerate(id_list):
            if i >= len(bboxes):
                break
            if sprite_id not in sprites:
                # New sprite not yet in registry -- add it
                print(f"  NEW sprite {sprite_id} at region {i}")
                sprites[sprite_id] = {
                    "source_sheet": sheet_id,
                    "pixel_rect": list(bboxes[i]),
                    "asset_slot": "unknown",
                    "condition": "clean",
                    "runtime_status": "pending_alpha_conversion",
                }
                upgraded += 1
                continue

            entry = sprites[sprite_id]
            was_estimated = entry.get("estimated", False)
            # Update pixel_rect
            entry["pixel_rect"] = list(bboxes[i])
            # Remove estimated flag if it was set
            if was_estimated:
                del entry["estimated"]
                upgraded += 1
                print(f"  upgraded {sprite_id}  rect={list(bboxes[i])}")

        print(f"  {upgraded} sprites upgraded for {sheet_id}")
        total_upgraded += upgraded

    registry["status"] = "source_detected_partial_mapping_v2"
    registry["pipeline_note"] = (
        "5 sheets re-detected with DILATION_ITERS=4 (calibrate_rects.py). "
        "pixel_rects marked 'estimated: true' have been updated where new "
        "detection found individual regions."
    )

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    print(f"\nWrote {REGISTRY_PATH}")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print("\n=== SUMMARY ===")
    for sheet_id in REDETECT_SHEETS:
        old_c = old_counts.get(sheet_id, "?")
        new_c = len(new_regions.get(sheet_id, []))
        exp_c = EXPECTED_COUNTS.get(sheet_id, "?")
        print(f"  {sheet_id:25s}  {old_c:>3} -> {new_c:>3}  (expected ~{exp_c})")
    print(f"\n  Total sprites upgraded from estimated -> exact: {total_upgraded}")


if __name__ == "__main__":
    main()
