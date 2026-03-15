#!/usr/bin/env python3
"""
Background worker for exporting animated GIFs.

Supports optional smart cropping (union bounding box across all frames)
and nearest-neighbor upscaling for crisp pixel art output.
"""

import os

from PyQt6.QtCore import pyqtSignal  # pylint: disable=no-name-in-module

from SF3FSPLORERGUI.src.core.workers.base_worker import BaseWorker

try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore


class GifExportWorker(BaseWorker):
    """Background worker for exporting animated GIFs"""

    gif_created = pyqtSignal(str)  # output_path
    export_error = pyqtSignal(str)  # error message
    export_progress = pyqtSignal(int, int, str)  # current, total, message

    def __init__(
        self,
        frame_paths: list[str],
        output_path: str,
        durations: list[int] | int = 100,
        loop: int = 0,
        smart_crop: bool = False,
        scale_factor: int = 1,
    ):
        """
        Initialize the GIF export worker.

        Args:
            frame_paths: List of file paths to the frames
            output_path: Path to save the GIF file
            durations: Per-frame durations in ms (list), or single value for all frames
            loop: Number of loops (0 = infinite)
            smart_crop: If True, auto-crop transparent borders using union bbox
            scale_factor: Nearest-neighbor upscale multiplier (1 = no upscale)
        """
        super().__init__()
        self.frame_paths = frame_paths
        self.output_path = output_path
        # Normalize to list
        if isinstance(durations, int):
            self.durations = [max(20, durations)] * len(frame_paths)
        else:
            self.durations = [max(20, d) for d in durations]
        self.loop = loop
        self.smart_crop = smart_crop
        self.scale_factor = max(1, scale_factor)
        self.set_timeout(300)  # 5 minutes timeout

    def _do_work(self):
        """Execute the export process"""
        if not PILLOW_AVAILABLE:
            msg = "Pillow library is not available. Cannot export GIF."
            self.export_error.emit(msg)
            raise ImportError(msg)

        return self._process_frames()

    def _compute_union_bbox(self, frame_paths: list[str]) -> tuple[int, int, int, int] | None:
        """Compute the union bounding box across all frames.

        Finds the tightest rectangle that contains all non-transparent
        pixels across ALL frames. This ensures consistent cropping
        so the character doesn't appear to jump between frames.

        Args:
            frame_paths: Paths to frame PNGs

        Returns:
            (left, top, right, bottom) bbox or None if all frames are empty
        """
        union_left = float("inf")
        union_top = float("inf")
        union_right = 0
        union_bottom = 0
        found_any = False
        img_w, img_h = 0, 0

        total = len(frame_paths)
        for i, path in enumerate(frame_paths):
            if self.is_cancelled():
                return None

            try:
                with Image.open(path) as img:
                    img = img.convert("RGBA")
                    img_w, img_h = img.size
                    bbox = img.getbbox()  # Returns (left, upper, right, lower) or None
                    if bbox:
                        found_any = True
                        union_left = min(union_left, bbox[0])
                        union_top = min(union_top, bbox[1])
                        union_right = max(union_right, bbox[2])
                        union_bottom = max(union_bottom, bbox[3])
            except (OSError, ValueError):
                continue

            if i % 20 == 0:
                self.export_progress.emit(i, total * 2, f"Analyzing frame {i + 1}/{total}...")

        if not found_any:
            return None

        # Add padding (4px each side) for visual comfort
        padding = 4
        union_left = max(0, int(union_left) - padding)
        union_top = max(0, int(union_top) - padding)
        union_right = min(img_w, int(union_right) + padding)
        union_bottom = min(img_h, int(union_bottom) + padding)

        return (union_left, union_top, union_right, union_bottom)

    def _process_frames(self):
        """Process frames and save GIF"""
        if not self.frame_paths:
            msg = "No frames to export."
            self.export_error.emit(msg)
            raise ValueError(msg)

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        total_frames = len(self.frame_paths)

        # Pass 1: Compute union bounding box (if smart crop enabled)
        crop_bbox = None
        if self.smart_crop:
            self.export_progress.emit(0, total_frames * 2, "Computing crop region...")
            crop_bbox = self._compute_union_bbox(self.frame_paths)
            if crop_bbox is None and not self.is_cancelled():
                self.logger.warning("All frames appear empty, skipping smart crop")

        if self.is_cancelled():
            return None

        # Pass 2: Load, crop, scale, quantize
        frames = []
        progress_offset = total_frames if self.smart_crop else 0

        self.export_progress.emit(progress_offset, progress_offset + total_frames, "Loading frames...")

        for i, frame_path in enumerate(self.frame_paths):
            if self.is_cancelled():
                return None

            try:
                with Image.open(frame_path) as img:
                    img = img.convert("RGBA")

                    # Smart crop to union bbox
                    if crop_bbox is not None:
                        img = img.crop(crop_bbox)

                    # Nearest-neighbor upscale
                    if self.scale_factor > 1:
                        new_w = img.width * self.scale_factor
                        new_h = img.height * self.scale_factor
                        img = img.resize((new_w, new_h), Image.NEAREST)

                    # 1. Extract alpha channel
                    alpha = img.getchannel("A")

                    # 2. Convert to RGB and quantize to 255 colors
                    frame = img.convert("RGB").quantize(colors=255, method=2)

                    # 3. Create transparency mask
                    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)

                    # 4. Paste transparency index
                    frame.paste(255, (0, 0), mask)

                    frames.append(frame)

                self.export_progress.emit(
                    progress_offset + i + 1,
                    progress_offset + total_frames,
                    f"Processed frame {i + 1}/{total_frames}",
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.warning("Failed to load frame %s: %s", frame_path, e)
                continue

        if not frames:
            msg = "Failed to load any frames."
            self.export_error.emit(msg)
            raise ValueError(msg)

        if self.is_cancelled():
            return None

        self.export_progress.emit(
            progress_offset + total_frames,
            progress_offset + total_frames,
            "Saving GIF...",
        )

        # Build per-frame duration list matching the actual frames loaded
        # (some frames may have been skipped on error)
        frame_durations = self.durations[:len(frames)]
        # Pad if needed
        while len(frame_durations) < len(frames):
            frame_durations.append(frame_durations[-1] if frame_durations else 100)

        # Save as GIF
        frames[0].save(
            self.output_path,
            save_all=True,
            append_images=frames[1:],
            optimize=False,
            duration=frame_durations,
            loop=self.loop,
            transparency=255,
            disposal=2,
        )

        self.gif_created.emit(self.output_path)
        return self.output_path
