"""Optional third-party UI packages. The app works without them, with reduced features.

* Pillow       -> JPEG thumbnails and large photo previews      (pip install pillow)
* tkinterdnd2  -> drag & drop photos from your file manager      (pip install tkinterdnd2)

Import the HAS_* flags and check them before using the optional names.
"""

try:
    from PIL import Image, ImageOps, ImageTk
    HAS_PIL = True
except ImportError:  # pragma: no cover - depends on the user's machine
    Image = ImageOps = ImageTk = None
    HAS_PIL = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:  # pragma: no cover
    DND_FILES = TkinterDnD = None
    HAS_DND = False

__all__ = ["HAS_PIL", "HAS_DND", "Image", "ImageOps", "ImageTk", "DND_FILES", "TkinterDnD"]
