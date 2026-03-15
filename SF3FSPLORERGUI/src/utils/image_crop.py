"""
Shared image cropping utilities for the Character Editor.

Provides auto-crop functions for both QPixmap (main thread) and QImage
(worker threads) to remove transparent borders from sprite frames.
"""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap


def auto_crop_pixmap(pixmap: QPixmap, padding: int = 0) -> QPixmap:
    """Crop a QPixmap to remove transparent borders.

    Args:
        pixmap: Source pixmap with potential transparent margins
        padding: Extra pixels to keep around the content (default 0)

    Returns:
        Cropped pixmap with transparent borders removed, or original if
        cropping fails or the image is fully transparent.
    """
    if pixmap.isNull():
        return pixmap

    image = pixmap.toImage()
    if image.isNull():
        return pixmap

    bbox = _find_content_bbox(image)
    if bbox is None:
        return pixmap

    x_min, y_min, x_max, y_max = bbox
    width = image.width()
    height = image.height()

    # Apply padding
    if padding > 0:
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(width - 1, x_max + padding)
        y_max = min(height - 1, y_max + padding)

    crop_w = x_max - x_min + 1
    crop_h = y_max - y_min + 1
    if crop_w <= 0 or crop_h <= 0:
        return pixmap

    return pixmap.copy(x_min, y_min, crop_w, crop_h)


def auto_crop_image(image: QImage) -> QImage:
    """Crop a QImage to remove transparent borders.

    Thread-safe variant that operates on QImage instead of QPixmap,
    allowing use on worker threads.

    Args:
        image: The QImage to crop

    Returns:
        Cropped QImage with transparent borders removed
    """
    if image.isNull():
        return image

    bbox = _find_content_bbox(image)
    if bbox is None:
        return image

    x_min, y_min, x_max, y_max = bbox
    crop_w = x_max - x_min + 1
    crop_h = y_max - y_min + 1
    if crop_w <= 0 or crop_h <= 0:
        return image

    return image.copy(x_min, y_min, crop_w, crop_h)


def _find_content_bbox(image: QImage) -> tuple[int, int, int, int] | None:
    """Find the bounding box of non-transparent content in a QImage.

    Args:
        image: QImage to analyze (will be converted to RGBA)

    Returns:
        (x_min, y_min, x_max, y_max) or None if fully transparent
    """
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = image.width()
    height = image.height()

    ptr = image.bits()
    if ptr is None:
        return None
    ptr.setsize(height * image.bytesPerLine())

    # PyQt6 voidptr becomes a buffer after setsize() but stubs don't reflect this
    buffer_data = bytes(ptr)  # type: ignore[call-overload]
    arr = np.frombuffer(buffer_data, dtype=np.uint8).reshape(
        (height, image.bytesPerLine())
    )
    # Extract just the RGBA channels (4 bytes per pixel)
    arr = arr[:, : width * 4].reshape((height, width, 4))

    alpha = arr[:, :, 3]
    non_transparent = np.where(alpha > 0)

    if len(non_transparent[0]) == 0:
        return None

    y_min = int(non_transparent[0].min())
    y_max = int(non_transparent[0].max())
    x_min = int(non_transparent[1].min())
    x_max = int(non_transparent[1].max())

    return (x_min, y_min, x_max, y_max)
