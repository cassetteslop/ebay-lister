"""Turn packaging/windows/icon.png (square, 256x256 or larger) into ebay_lister.ico for the .exe.

Does nothing if there's no icon.png - the build then uses PyInstaller's default icon.
Needs Pillow (installed by requirements-build.txt).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    src = os.path.join(HERE, "icon.png")
    if not os.path.exists(src):
        print("No packaging/windows/icon.png - using the default icon.")
        return 0
    from PIL import Image
    img = Image.open(src).convert("RGBA")
    dest = os.path.join(HERE, "ebay_lister.ico")
    img.save(dest, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon written to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
