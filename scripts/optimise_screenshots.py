"""Downscale and convert captured screenshots to WebP.

Playwright can only write PNG or JPEG, and a 2x-scale PNG of a dark, gradient
heavy UI is ~2-3 MB each — 36 MB for the set, which is far too much to carry in
a git repository. WebP at 1x brings the same set under 1 MB with no visible
loss at README display size, and GitHub renders WebP in Markdown natively.

Run it after `scripts/capture_screenshots.mjs`:

    python scripts/optimise_screenshots.py

Requires Pillow (a tooling-only dependency, deliberately not in
requirements.txt):

    pip install Pillow
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - tooling dependency
    sys.exit("Pillow is required: pip install Pillow")

SCREENSHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

#: Wider than any README column, so the images stay crisp without the 2x bulk.
MAX_WIDTH = 1600
QUALITY = 88


def main() -> int:
    sources = sorted(SCREENSHOTS.glob("*.png"))
    if not sources:
        print(f"No PNGs in {SCREENSHOTS}. Run scripts/capture_screenshots.mjs first.")
        return 0

    before = after = 0

    for path in sources:
        original_size = path.stat().st_size
        before += original_size

        image = Image.open(path).convert("RGB")
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            image = image.resize(
                (MAX_WIDTH, round(image.height * ratio)), Image.LANCZOS
            )

        destination = path.with_suffix(".webp")
        image.save(destination, "WEBP", quality=QUALITY, method=6)
        after += destination.stat().st_size
        path.unlink()

        print(
            f"  {path.name:<34} "
            f"{original_size / 1024:7.0f} KB -> {destination.stat().st_size / 1024:6.0f} KB"
        )

    print(f"\nTotal {before / 1024 / 1024:.1f} MB -> {after / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
