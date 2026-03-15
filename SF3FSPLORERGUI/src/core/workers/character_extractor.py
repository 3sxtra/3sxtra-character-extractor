"""Worker module for Character extraction tasks."""

import os
import subprocess
import sys
import time

from PyQt6.QtCore import pyqtSignal

# sf33rd library imports moved to method level to avoid Qt conflicts
from SF3FSPLORERGUI.src.utils.compatibility import SF33RD_AVAILABLE

from .base_worker import BaseWorker

if SF33RD_AVAILABLE:
    from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source as GET_AFS_DATA_SOURCE  # noqa: N812
    from sf33rd.core.data_model import character_data as CHARACTER_DATA  # noqa: N812
else:
    CHARACTER_DATA = None  # type: ignore
    GET_AFS_DATA_SOURCE = None  # type: ignore


class CharacterExtractionWorker(BaseWorker):
    """
    Worker for extracting character sprites from game assets.
    """

    # Custom signals
    extraction_progress = pyqtSignal(int, int, str)  # current, total, message
    extraction_complete = pyqtSignal(str, str)  # character_name, output_path

    def __init__(self):
        super().__init__()
        self.character_name = ""
        self.palette_index = 0
        self.effect_mode: str | None = None  # NEW: PalMod-style effect
        self.custom_palette_path = None
        self.output_dir = ""
        self.game_root = ""

    def set_params(
        self,
        character_name: str,
        output_dir: str,
        palette_index: int = 0,
        effect_mode: str | None = None,
        custom_palette_path: str | None = None,
        game_root: str = "",
    ):
        """Set extraction parameters.

        Args:
            character_name: Name of the character to extract
            output_dir: Directory to output extracted files
            palette_index: Costume color index (0-6 for LP-EX)
            effect_mode: Optional effect type ("burned", "frozen", "grey_tint", "sa_parry")
            custom_palette_path: Optional path to custom palette file
            game_root: Root directory of the game files
        """
        # pylint: disable=too-many-positional-arguments
        # pylint: disable=too-many-arguments
        self.character_name = character_name
        self.output_dir = output_dir
        self.palette_index = palette_index
        self.effect_mode = effect_mode
        self.custom_palette_path = custom_palette_path
        self.game_root = game_root

    def _do_work(self):
        """Execute the extraction process"""
        self.update_status(f"Starting extraction for {self.character_name}...")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Check if sf33rd is available
        try:
            self._extract_real()
        except ImportError:
            self.logger.warning("sf33rd library not available, running simulation")
            self._simulate_extraction()

        if not self._is_cancelled:
            self.extraction_complete.emit(self.character_name, self.output_dir)
            self.update_status("Extraction completed successfully")
            return float(100)  # Complete
        return float(0)

    def _extract_real(self):
        """Perform actual extraction using sf33rd library in subprocess"""
        self.update_status("Initializing sf33rd extractor...")

        if CHARACTER_DATA is None:
            raise RuntimeError(
                "Failed to import sf33rd.core.data_model. Ensure the library is installed and accessible."
            )

        # Get data source - will auto-discover AFS archive or extracted folder
        data_source = GET_AFS_DATA_SOURCE()
        source_type = data_source.source_type
        source_path = data_source.source_path

        # --- Step 1: Unpack Sprites ---
        self.extraction_progress.emit(0, 100, f"Step 1/2: Extracting {self.character_name} sprites...")

        sprite_output_dir = os.path.join(self.output_dir, "sprites")
        if not os.path.exists(sprite_output_dir):
            os.makedirs(sprite_output_dir)

        # Build subprocess script that uses AfsDataSource for smart extraction
        unpack_script = f"""
import sys
sys.path.insert(0, r'{self.game_root}')
from sf33rd.parsers.texture_unpacker import unpack_character_sprites_indexed
from sf33rd.core.afs_data_source import AfsDataSource, FolderDataSource, ArchiveDataSource

# Recreate the data source in the subprocess
source_type = {repr(source_type)}
source_path = {repr(source_path)}

if source_type == "archive":
    data_source = ArchiveDataSource(source_path)
else:
    data_source = FolderDataSource(source_path)

# Use the data source for extraction
unpack_character_sprites_indexed(
    character_name={repr(self.character_name)},
    output_dir={repr(sprite_output_dir)},
    max_sprites=100000,
    override_palette_path={repr(self.custom_palette_path)},
    data_source=data_source
)
"""

        result_unpack = subprocess.run(
            [sys.executable, "-c", unpack_script], capture_output=True, text=True, cwd=self.game_root, check=False
        )

        if result_unpack.returncode != 0:
            raise RuntimeError(f"Sprite extraction failed: {result_unpack.stderr}")

        self.extraction_progress.emit(50, 100, "Sprite extraction complete.")

        # Check for cancellation before starting the next step
        if self._is_cancelled:
            self.update_status("Extraction cancelled after unpacking.")
            return

        # --- Step 2: Recompose Frames ---
        self.extraction_progress.emit(50, 100, f"Step 2/2: Recomposing {self.character_name} animation frames...")

        char_info = CHARACTER_DATA.get(self.character_name)
        if not char_info or "tex" not in char_info:
            self.logger.warning("No 'tex' file defined for %s. Skipping frame recomposition.", self.character_name)
            self.extraction_progress.emit(100, 100, "Skipped frame recomposition (no 'tex' file).")
            return

        tex_file = str(char_info["tex"])

        # Get tex_path based on source type
        if source_type == "folder":
            tex_path = os.path.join(source_path, tex_file)
            if not os.path.exists(tex_path):
                raise FileNotFoundError(f"Texture/Layout file not found: {tex_path}")
        else:
            # For archive: file was already extracted to temp in Step 1, or
            # extract now
            import tempfile  # pylint: disable=import-outside-toplevel

            tex_data = data_source.get_file_data(tex_file)
            temp_dir = tempfile.mkdtemp(prefix="sf33rd_recompose_")
            tex_path = os.path.join(temp_dir, tex_file)
            with open(tex_path, "wb") as f:
                f.write(tex_data)

        frames_output_dir = os.path.join(self.output_dir, "frames")
        if not os.path.exists(frames_output_dir):
            os.makedirs(frames_output_dir)

        # Get tex_offset for proper display dimension handling
        tex_offset = char_info.get("to_tex", 0)

        recompose_script = f"""
import sys
sys.path.insert(0, r'{self.game_root}')
from sf33rd.operations.frame_recomposer import recompose_frames

recompose_frames(
    pl_file_path={repr(tex_path)},
    sprite_dir={repr(sprite_output_dir)},
    output_dir={repr(frames_output_dir)},
    verbose=False,
    tex_offset={tex_offset},
    use_runtime_palette=True,
    base_style={self.palette_index}
)
"""

        result_recompose = subprocess.run(
            [sys.executable, "-c", recompose_script], capture_output=True, text=True, cwd=self.game_root, check=False
        )

        if result_recompose.returncode != 0:
            # Check for a common warning vs. a hard error
            if "Could not read entry" in result_recompose.stderr and "stopping frame" in result_recompose.stderr:
                self.logger.warning(
                    "Frame recomposition for %s finished with non-critical errors. Some frames may be missing.",
                    self.character_name,
                )
            else:
                raise RuntimeError(f"Frame recomposition failed: {result_recompose.stderr}")

        self.extraction_progress.emit(100, 100, "Frame recomposition complete.")

    def _simulate_extraction(self):
        """Simulate extraction for testing/demo purposes"""

        total_frames = 50

        for i in range(total_frames):
            if self._is_cancelled:
                return

            time.sleep(0.05)  # Simulate work

            # Create dummy file
            filename = f"{self.character_name}_{i:03d}.png"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("Dummy sprite data")

            progress = int((i + 1) / total_frames * 100)
            self.set_progress(progress, 100)
            self.extraction_progress.emit(i + 1, total_frames, f"Extracted {filename}")

        self.set_progress(100, 100)
