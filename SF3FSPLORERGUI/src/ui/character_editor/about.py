#!/usr/bin/env python3
"""
About dialog for Character Extractor - inherits from BaseAboutDialog.
"""

from SF3FSPLORERGUI.src.ui.dialogs.about import BaseAboutDialog


class CharacterExtractorAboutDialog(BaseAboutDialog):
    """About dialog for SF3:3rd Character Extractor."""

    WINDOW_TITLE = "About Character Extractor"
    APP_NAME = "SF3:3rd Character Extractor"
    APP_DESCRIPTION = (
        "A dedicated tool for extracting and viewing character animations "
        "from Street Fighter III: 3rd Strike. Extract sprites, play animation "
        "sequences at authentic game timing, and export to GIF."
    )
    FEATURES = [
        "Character Extraction - Extract all sprites and frames for any character",
        "Animation Playback - View sequences at authentic 60 FPS game timing",
        "Palette Preview - Real-time palette selection with 6 color variants",
        "Frame Mosaic - Browse all extracted frames in a visual grid",
        "Sequence Browser - Navigate ROM-parsed animation sequences",
        "GIF Export - Export any sequence as an animated GIF file",
    ]
    MAIN_DEPENDENCIES = {
        "PyQt6": "6.5+ - GUI framework",
        "sf33rd": "Game asset parsing library",
        "numpy": "Image array operations",
        "pillow": "Image processing and GIF export",
    }

    @staticmethod
    def show_about_dialog(parent=None):
        """Static method to show the about dialog."""
        dialog = CharacterExtractorAboutDialog(parent)
        dialog.exec()
