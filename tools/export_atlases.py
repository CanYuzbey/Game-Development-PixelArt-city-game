"""
export_atlases.py
Atlas Packer — reads sprite_registry.json, crops sprites from RGBA source sheets,
bin-packs them into category-based runtime atlas PNGs, and saves companion JSON manifests.
"""

import json
import sys
import os
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT   = r"C:\Users\xxx\Desktop\GameDev"
SOURCE_DIR     = os.path.join(PROJECT_ROOT, "assets", "source_rgba")
RUNTIME_DIR    = os.path.join(PROJECT_ROOT, "assets", "runtime")
MANIFEST_DIR   = os.path.join(PROJECT_ROOT, "assets", "manifests")
REGISTRY_PATH  = os.path.join(MANIFEST_DIR, "sprite_registry.json")

# ---------------------------------------------------------------------------
# Atlas grouping
# ---------------------------------------------------------------------------
ATLAS_GROUPS = {
    "terrain": {
        "terrain/exterior",
        "terrain/water",
    },
    "buildings": {
        "building/office",
        "building/apartment",
        "building/house",
        "building/shop",
        "building/restaurant",
        "building/market",
        "building/bank",
        "building/civic",
    },
    "roofs": {
        "building/roof",
    },
    "landmarks": None,          # handled specially: "landmark/*"
    "coastal": {
        "coast/beach",
        "coast/seawall",
        "coast/dock",
        "coast/cliff",
    },
    "road_diagonals": {
        "street/road",
        "street/sidewalk",
    },
    "park": {
        "landscape/park",
        "prop/park",
    },
    "kits": {
        "prop/facade_kit",
    },
    "props": {
        "prop/street",
    },
    "overlays": {
        "overlay/lighting",
        "overlay/shadow",
        "overlay/weathering",
    },
}

MAX_ATLAS_WIDTH = 2048
PADDING = 2


def slot_to_atlas(asset_slot: str) -> str | None:
    """Return atlas name for a given asset_slot, or None if unmapped."""
    if asset_slot == "unknown":
        return None
    # Check exact sets first
    for atlas_name, slots in ATLAS_GROUPS.items():
        if slots is None:
            continue  # landmarks handled below
        if asset_slot in slots:
            return atlas_name
    # Landmarks: any "landmark/*"
    if asset_slot.startswith("landmark/"):
        return "landmarks"
    return None


def shelf_pack(sprites_with_images):
    """
    Shelf-pack algorithm.
    sprites_with_images: list of (sprite_id, PIL.Image)
    Returns: list of (sprite_id, x, y, w, h), (atlas_width, atlas_height)
    """
    # Sort by height descending
    items = sorted(sprites_with_images, key=lambda t: t[1].height, reverse=True)

    placements = []
    x = 0
    y = 0
    row_height = 0

    for sprite_id, img in items:
        w, h = img.size
        if x + w > MAX_ATLAS_WIDTH:
            # New row
            y += row_height + PADDING
            x = 0
            row_height = h
        if row_height == 0:
            row_height = h
        placements.append((sprite_id, x, y, w, h))
        x += w + PADDING

    atlas_height = y + row_height
    return placements, (MAX_ATLAS_WIDTH, atlas_height)


def load_source_sheets(registry):
    """Pre-load all referenced source sheets. Returns dict sheet_name -> PIL.Image or None."""
    sheet_names = set()
    for sprite_id, info in registry["sprites"].items():
        sheet_names.add(info["source_sheet"])

    sheets = {}
    for name in sheet_names:
        path = os.path.join(SOURCE_DIR, f"{name}.png")
        if not os.path.exists(path):
            print(f"  [WARNING] Source sheet not found: {path}")
            sheets[name] = None
        else:
            sheets[name] = Image.open(path).convert("RGBA")
    return sheets


def crop_sprite(sheet_img, sprite_id, pixel_rect):
    """
    Crop sprite from sheet. Clamps to image bounds if out of range.
    Returns (PIL.Image, was_clamped, is_fully_transparent)
    """
    sx, sy, sw, sh = pixel_rect
    img_w, img_h = sheet_img.size

    # Clamp
    x1 = max(0, sx)
    y1 = max(0, sy)
    x2 = min(img_w, sx + sw)
    y2 = min(img_h, sy + sh)

    was_clamped = (x1 != sx or y1 != sy or x2 != sx + sw or y2 != sy + sh)
    if was_clamped:
        print(f"  [WARNING] Sprite '{sprite_id}' pixel_rect [{sx},{sy},{sw},{sh}] "
              f"clamped to [{x1},{y1},{x2-x1},{y2-y1}] (source {img_w}x{img_h})")

    if x2 <= x1 or y2 <= y1:
        print(f"  [WARNING] Sprite '{sprite_id}' has zero-area crop after clamping — skipping")
        return None, was_clamped, True

    cropped = sheet_img.crop((x1, y1, x2, y2))

    # Check fully transparent
    arr = np.array(cropped)
    is_fully_transparent = bool((arr[:, :, 3] == 0).all())
    if is_fully_transparent:
        print(f"  [WARNING] Sprite '{sprite_id}' crop is entirely transparent (alpha=0)")

    return cropped, was_clamped, is_fully_transparent


def export_atlas(atlas_name, sprite_pairs, registry_data):
    """
    Bin-pack sprites into an atlas PNG + JSON manifest.
    sprite_pairs: list of (sprite_id, PIL.Image)
    registry_data: dict being mutated to add atlas_file/atlas_rect/runtime_status
    Returns: (placements, atlas_size) or None if empty.
    """
    if not sprite_pairs:
        print(f"  [SKIP] Atlas '{atlas_name}' has no sprites.")
        return None

    placements, (aw, ah) = shelf_pack(sprite_pairs)

    atlas_img = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))

    # Build a quick lookup: id -> PIL.Image
    img_lookup = {sid: img for sid, img in sprite_pairs}

    sprites_json = {}
    for sprite_id, x, y, w, h in placements:
        img = img_lookup[sprite_id]
        atlas_img.paste(img, (x, y))
        sprites_json[sprite_id] = [x, y, w, h]

        # Update registry
        registry_data["sprites"][sprite_id]["atlas_file"] = f"{atlas_name}.atlas.png"
        registry_data["sprites"][sprite_id]["atlas_rect"] = [x, y, w, h]
        registry_data["sprites"][sprite_id]["runtime_status"] = "exported"

    atlas_file = os.path.join(RUNTIME_DIR, f"{atlas_name}.atlas.png")
    atlas_img.save(atlas_file, "PNG")

    manifest = {
        "schema": "atlas_manifest.v1",
        "atlas_id": atlas_name,
        "file": f"runtime/{atlas_name}.atlas.png",
        "size": [aw, ah],
        "sprite_count": len(placements),
        "sprites": sprites_json,
    }
    manifest_file = os.path.join(MANIFEST_DIR, f"{atlas_name}_atlas.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Atlas '{atlas_name}': {aw}x{ah}px, {len(placements)} sprites -> "
          f"runtime/{atlas_name}.atlas.png")

    return placements, (aw, ah)


def main():
    print("=== Atlas Packer ===")
    print(f"Source sheets : {SOURCE_DIR}")
    print(f"Output runtime: {RUNTIME_DIR}")
    print(f"Output manifest: {MANIFEST_DIR}")
    print()

    # Load registry
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)

    print(f"Loaded registry: {len(registry['sprites'])} sprites declared")
    print()

    # Pre-load source sheets
    print("Loading source sheets...")
    sheets = load_source_sheets(registry)
    missing_sheets = {k for k, v in sheets.items() if v is None}
    print(f"  Loaded {sum(1 for v in sheets.values() if v is not None)} sheets, "
          f"{len(missing_sheets)} missing: {missing_sheets if missing_sheets else 'none'}")
    print()

    # Crop sprites and assign to atlases
    atlas_buckets = {name: [] for name in ATLAS_GROUPS}

    total_sprites = len(registry["sprites"])
    skipped_missing_sheet = 0
    skipped_zero_area = 0
    transparent_warned = 0
    clamped_warned = 0
    skipped_unmapped = 0

    print("Cropping sprites...")
    for sprite_id, info in registry["sprites"].items():
        sheet_name = info["source_sheet"]
        pixel_rect = info["pixel_rect"]  # [x, y, w, h]
        asset_slot = info.get("asset_slot", "unknown")

        # Check sheet exists
        if sheets.get(sheet_name) is None:
            # Already warned at load time
            skipped_missing_sheet += 1
            continue

        # Determine atlas
        atlas_name = slot_to_atlas(asset_slot)
        if atlas_name is None:
            skipped_unmapped += 1
            continue

        sheet_img = sheets[sheet_name]
        cropped, was_clamped, is_transparent = crop_sprite(sheet_img, sprite_id, pixel_rect)

        if was_clamped:
            clamped_warned += 1
        if is_transparent:
            transparent_warned += 1

        if cropped is None:
            skipped_zero_area += 1
            continue

        atlas_buckets[atlas_name].append((sprite_id, cropped))

    print()

    # Export atlases
    print("Exporting atlases...")
    total_exported = 0
    for atlas_name in ATLAS_GROUPS:
        result = export_atlas(atlas_name, atlas_buckets[atlas_name], registry)
        if result is not None:
            total_exported += len(result[0])

    print()

    # Save updated registry
    print("Saving updated sprite_registry.json...")
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    # Count exported in registry
    exported_count = sum(
        1 for info in registry["sprites"].values()
        if info.get("runtime_status") == "exported"
    )

    print()
    print("=== Summary ===")
    print(f"Total sprites in registry  : {total_sprites}")
    print(f"  Skipped (missing sheet)  : {skipped_missing_sheet}")
    print(f"  Skipped (unmapped slot)  : {skipped_unmapped}")
    print(f"  Skipped (zero-area crop) : {skipped_zero_area}")
    print(f"  Warnings (clamped rect)  : {clamped_warned}")
    print(f"  Warnings (transparent)   : {transparent_warned}")
    print(f"Total sprites exported     : {total_exported}")
    print(f"registry runtime_status=exported: {exported_count}")


if __name__ == "__main__":
    main()
