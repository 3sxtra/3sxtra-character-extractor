"""Worker module for Frame recomposition tasks."""

import os
import time

from PyQt6.QtCore import pyqtSignal

# Try to import sf33rd library
# Try to import sf33rd library
from SF3FSPLORERGUI.src.utils.compatibility import SF33RD_AVAILABLE

from .base_worker import BaseWorker

if SF33RD_AVAILABLE:
    from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source as GET_AFS_DATA_SOURCE  # noqa: N812
    from sf33rd.core.data_model import character_data as CHARACTER_DATA  # noqa: N812
    from sf33rd.operations.frame_recomposer import recompose_frames as RECOMPOSE_FRAMES  # noqa: N812
else:
    CHARACTER_DATA = None  # type: ignore
    RECOMPOSE_FRAMES = None  # type: ignore
    GET_AFS_DATA_SOURCE = None  # type: ignore


class FrameRecompositionWorker(BaseWorker):
    """
    Worker for recomposing character sprites into full frames.
    """

    # Custom signals
    recomposition_complete = pyqtSignal(str, str)  # character_name, output_path

    def __init__(self):
        super().__init__()
        self.character_name = ""
        self.sprite_dir = ""
        self.output_dir = ""
        self.game_root = ""

    def set_params(self, character_name: str, sprite_dir: str, output_dir: str, game_root: str):
        """Set recomposition parameters"""
        self.character_name = character_name
        self.sprite_dir = sprite_dir
        self.output_dir = output_dir
        self.game_root = game_root

    def _do_work(self):
        """Execute the frame recomposition"""
        self.update_status(f"Starting frame recomposition for {self.character_name}...")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        if SF33RD_AVAILABLE:
            self._recompose_real()
        else:
            self._simulate_work()

        if not self._is_cancelled:
            self.recomposition_complete.emit(self.character_name, self.output_dir)
            self.update_status("Recomposition completed successfully")
            return float(100)
        return float(0)

    def _recompose_real(self):
        """Perform actual recomposition using sf33rd library"""
        if self.character_name not in CHARACTER_DATA:
            raise ValueError(f"Unknown character: {self.character_name}")

        char_info = CHARACTER_DATA[self.character_name]
        tex_filename = str(char_info["tex"])

        # Locate the TEX file using data source
        data_source = GET_AFS_DATA_SOURCE()

        # For folder mode, get path directly
        if data_source.source_type == "folder":
            tex_path = data_source.get_file_path(tex_filename)
            if not tex_path or not os.path.exists(tex_path):
                raise FileNotFoundError(f"TEX file not found: {tex_filename}")
        else:
            # Archive mode: extract to temp
            import tempfile  # pylint: disable=import-outside-toplevel

            tex_data = data_source.get_file_data(tex_filename)
            temp_dir = tempfile.mkdtemp(prefix="sf33rd_recompose_")
            tex_path = os.path.join(temp_dir, tex_filename)
            with open(tex_path, "wb") as f:
                f.write(tex_data)

        if not os.path.exists(self.sprite_dir):
            raise FileNotFoundError(f"Sprite directory not found at {self.sprite_dir}")

        self.update_status(f"Recomposing frames using {tex_filename}...")
        self.set_progress(0, 0)  # Indeterminate

        tex_offset_val = char_info.get("to_tex", 0)
        tex_offset = tex_offset_val if isinstance(tex_offset_val, int) else 0

        RECOMPOSE_FRAMES(
            tex_path,
            self.sprite_dir,
            self.output_dir,
            use_runtime_palette=True,
            tex_offset=tex_offset,
        )

        self.set_progress(100, 100)

    def _simulate_work(self):
        """Simulate work for testing"""
        self.update_status("Simulating frame recomposition...")
        time.sleep(1)
        self.set_progress(50, 100)
        time.sleep(1)
        self.set_progress(100, 100)
