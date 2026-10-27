#!/usr/bin/env python3
"""Build the release zip: dist/EVA-Responsive-<version>.zip

  python release.py 1.0.0

The zip holds the built patch, the two fonts with their licenses, install.ps1 and the
README. The fonts are not in git: put NotoSerifCJKjp-Black.otf and
ShipporiMinchoB1-ExtraBold.ttf in fonts/ first (see fonts/README.md).
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "EVA-Responsive"
FONTS = ["NotoSerifCJKjp-Black.otf", "ShipporiMinchoB1-ExtraBold.ttf", "OFL-noto-cjk.txt", "OFL-shippori.txt"]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    version = sys.argv[1].lstrip("v")
    missing = [f for f in FONTS if not (HERE / "fonts" / f).exists()]
    if missing:
        raise SystemExit(f"missing in fonts/: {missing}")
    root = f"{NAME}-{version}"
    out = HERE / "dist" / f"{root}.zip"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # The paths written in the .wire are rewritten by install.ps1.
        subprocess.run([sys.executable, str(HERE / "build_wire.py"), "--patches", tmp], check=True)
        patch = Path(tmp) / NAME
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(patch.iterdir()):
                z.write(f, f"{root}/{NAME}/{f.name}")
            for f in FONTS:
                z.write(HERE / "fonts" / f, f"{root}/fonts/{f}")
            for f in ("install.ps1", "README.md", "LICENSE"):
                z.write(HERE / f, f"{root}/{f}")
    print(f"{out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
