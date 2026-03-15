"""
Background worker for loading and pre-processing mosaic frame thumbnails.

Loads PNG frames on a background thread using QImage (thread-safe),
performs auto-crop and scaling, then emits results for main-thread display.
"""

import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage

from SF3FSPLORERGUI.src.core.workers.base_worker import BaseWorker
from SF3FSPLORERGUI.src.utils.image_crop import auto_crop_image


class MosaicLoadWorker(BaseWorker):
    """Background worker for loading, cropping, and scaling mosaic thumbnails.

    Produces a list of (frame_index, QImage) tuples ready for main-thread
    conversion to QPixmap and display.
    """

    frames_loaded = pyqtSignal(list)  # list of (int, QImage) tuples

    def __init__(self):
        super().__init__()
        self._frames_dir = ""
        self._total_frames = 0
        self._thumbnail_size = 128
        self.set_timeout(120)

    def set_params(
        self, frames_dir: str, total_frames: int, thumbnail_size: int = 128
    ) -> None:
        """Configure the worker parameters.

        Args:
            frames_dir: Directory containing frame_N.png files
            total_frames: Total number of frames to load (0-indexed)
            thumbnail_size: Target height in pixels for thumbnails
        """
        self._frames_dir = frames_dir
        self._total_frames = total_frames
        self._thumbnail_size = thumbnail_size

    def _do_work(self):
        """Load, crop, and scale all frames."""
        results: list[tuple[int, QImage]] = []
        logger = logging.getLogger(self.__class__.__name__)

        for i in range(self._total_frames):
            if self.is_cancelled():
                logger.info(
                    "Mosaic loading cancelled at frame %d/%d", i, self._total_frames
                )
                return results

            frame_path = os.path.join(self._frames_dir, f"frame_{i}.png")
            if not os.path.exists(frame_path):
                continue

            image = QImage(frame_path)
            if image.isNull():
                continue

            cropped = auto_crop_image(image)

            if cropped.height() != self._thumbnail_size:
                cropped = cropped.scaledToHeight(
                    self._thumbnail_size,
                    Qt.TransformationMode.FastTransformation,
                )

            results.append((i, cropped))

            if i % 50 == 0:
                self.set_progress(i, self._total_frames)

        self.set_progress(self._total_frames, self._total_frames)
        logger.info("Loaded %d mosaic frames", len(results))
        self.frames_loaded.emit(results)
        return results
