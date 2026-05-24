"""
Validate raw existing-city asset sheets against the asset manifest.

This is a lightweight debug tool for generated/raw asset drops. It does not
slice sprites yet; it verifies that the current raw sheets are present and
records the known "not runtime ready" alpha state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "asset_manifest.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    issues: list[str] = []

    for sheet in manifest.get("raw_sheets", []):
        rel = sheet.get("file", "")
        path = ROOT / "assets" / rel
        if not path.exists():
            issues.append(f"missing:{rel}")
            continue

        with Image.open(path) as image:
            expected_size = tuple(sheet.get("size", []))
            if image.size != expected_size:
                issues.append(f"size:{rel}:{image.size}!={expected_size}")
            if image.mode != sheet.get("mode"):
                issues.append(f"mode:{rel}:{image.mode}!={sheet.get('mode')}")
            if "A" not in image.mode:
                print(f"WARN no-alpha: {rel}")

    if issues:
        for issue in issues:
            print(f"FAIL {issue}")
        return 1

    print("asset manifest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
