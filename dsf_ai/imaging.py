"""Image utilities: PDF rasterisation, blank-page removal, resizing, rotation fix."""
import io
import logging
from typing import List

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

BLANK_THRESHOLD = 0.005   # a page with < 0.5 % non-white pixels is considered blank
WHITE_LEVEL = 240


def pdf_to_images(pdf_path: str, dpi: int = 200, **kwargs) -> List[Image.Image]:
    from pdf2image import convert_from_path  # needs poppler-utils

    images = convert_from_path(pdf_path, dpi=dpi, fmt="png", **kwargs)
    logger.info("Rasterised %s at %d DPI → %d pages", pdf_path, dpi, len(images))
    return images


def dark_pixel_ratio(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"))
    return float((gray < WHITE_LEVEL).mean())


def is_blank(image: Image.Image, threshold: float = BLANK_THRESHOLD) -> bool:
    return dark_pixel_ratio(image) < threshold


def drop_blank_pages(images: List[Image.Image], threshold: float = BLANK_THRESHOLD) -> List[Image.Image]:
    kept = [img for img in images if not is_blank(img, threshold)]
    if len(kept) < len(images):
        logger.info("Removed %d blank pages → %d remaining", len(images) - len(kept), len(kept))
    return kept


def to_png_bytes(image: Image.Image, max_size: int = 2048) -> bytes:
    """Downscale so the longest side is ≤ max_size, then encode as PNG."""
    w, h = image.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def fix_rotation(img: np.ndarray) -> np.ndarray:
    """Rotate a portrait scan of a landscape form to landscape.

    The DSF statistical form is landscape with a bordered year box at the
    top centre. When a scan arrives in portrait, try both 90° rotations and
    keep the one with the most ink in that top-centre strip.
    """
    import cv2

    h, w = img.shape[:2]
    if h <= w:
        return img
    best, best_score = None, -1
    for rotated in (cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)):
        rh, rw = rotated.shape[:2]
        region = cv2.cvtColor(rotated[0:rh // 15, rw // 3:2 * rw // 3], cv2.COLOR_BGR2GRAY)
        score = int(np.sum(region < 100))
        if score > best_score:
            best_score, best = score, rotated
    return best


def prepare_form_image(path: str, quality: int = 92) -> bytes:
    """Load a form scan, fix its orientation, return JPEG bytes."""
    import cv2

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    img = fix_rotation(img)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError(f"Cannot encode image: {path}")
    return buf.tobytes()
