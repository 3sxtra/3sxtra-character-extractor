"""
Layout validation and constraint management for SF3:3rd Strike stages.

This module provides a clean interface to the stage layout database,
which defines hardware constraints like active texture slots and layer counts.
"""

import json
import logging
import os

from sf33rd.core.stage_data import bgtex_stage_gbix

logger = logging.getLogger(__name__)


class StageConstraintDB:
    """
    Interface to the stage layout constraint database.

    Provides methods for querying stage-specific constraints like layer counts,
    active texture slots, and validation of tile counts against hardware limits.
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize the constraint database.

        Args:
            db_path: Optional path to stage_layouts.json (auto-detected if None)
        """
        if db_path is None:
            # Auto-detect path relative to this module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, "..", "data", "stage_layouts.json")

        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Stage layouts database not found: {db_path}")

        with open(db_path, encoding="utf-8") as f:
            self._stages = json.load(f)

        # Create lookup dict for faster access
        self._stage_dict = {stage["stage_id"]: stage for stage in self._stages}

        # Load physics data
        physics_path = os.path.join(current_dir, "..", "data", "stage_physics.json")
        if os.path.exists(physics_path):
            with open(physics_path, encoding="utf-8") as f:
                self._physics = json.load(f)
        else:
            self._physics = {}
            logger.warning("Stage physics data not found: %s", physics_path)

        # Patch layouts with masks from bgtex_stage_gbix

        for stage in self._stages:
            stage_id = stage["stage_id"]
            if stage_id < len(bgtex_stage_gbix):
                masks = bgtex_stage_gbix[stage_id]

                for layer in stage["layers"]:
                    layer_idx = layer["layer_idx"]
                    if layer_idx < len(masks):
                        mask = masks[layer_idx]
                        # Update layer mask string
                        layer["texture_mask"] = f"{mask:#x}"

        # Override specific stage masks to unlock hidden slots for editing
        # Stage 0 Layer 1 has slots 23 and 31 disabled in original data, but we want to allow editing them.
        # UPDATE: Overriding the mask causes tile scrambling because the game logic expects specific GBIX ordering.
        # We must respect the original mask to ensure tiles are packed in the correct sequence.
        # self._override_mask(0, 1, 0xFFFFFFFF)

        logger.info("Loaded layout database: %s stages (Patched with 64-bit masks)", len(self._stages))

    def _override_mask(self, stage_id: int, layer_idx: int, new_mask: int):
        """Helper to override a specific layer mask."""
        stage = self._stage_dict.get(stage_id)
        if stage:
            for layer in stage["layers"]:
                if layer["layer_idx"] == layer_idx:
                    layer["texture_mask"] = f"{new_mask:#x}"
                    logger.info("Overridden mask for Stage %s Layer %s to %#x", stage_id, layer_idx, new_mask)
                    break

    def load_stage_layout(self, stage_id: int) -> dict | None:
        """
        Load the layout constraints for a specific stage.

        Args:
            stage_id: Stage ID (0-21)

        Returns:
            Dictionary containing stage layout data, or None if not found
        """
        return self._stage_dict.get(stage_id)

    def get_layer_count(self, stage_id: int) -> int:
        """
        Get the number of layers for a stage.

        Args:
            stage_id: Stage ID (0-21)

        Returns:
            Number of layers (1-3), or 0 if stage not found
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            return 0
        return int(layout.get("layer_count", 0))

    def parse_texture_mask(self, mask_str: str) -> int:
        """
        Convert a hex string mask to an integer.

        Args:
            mask_str: Hex string, e.g., "0xf0f0f0f0"

        Returns:
            Integer representation of the bitmask
        """
        return int(mask_str, 16)

    def get_active_slots_from_mask(self, mask: int) -> list[int]:
        """
        Get a list of active slot indices from a bitmask.

        Args:
            mask: 32-bit bitmask where set bit = active slot.
                  Interpreted MSB-first (Bit 31 = Slot 0).

        Returns:
            List of active slot indices (0-31)
        """
        active_slots = []

        for i in range(32):
            # Check bit (31 - i)
            if mask & (1 << (31 - i)):
                active_slots.append(i)

        return active_slots

    def get_active_slots(self, stage_id: int, layer_idx: int | None = None) -> list[int]:
        """
        Get active texture slots for a stage (optionally filtered by layer).

        Args:
            stage_id: Stage ID (0-21)
            layer_idx: Optional layer index to filter (None = all layers)

        Returns:
            List of active slot indices
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            return []

        all_active_slots = []

        for layer in layout["layers"]:
            if layer_idx is not None and layer["layer_idx"] != layer_idx:
                continue

            mask = self.parse_texture_mask(layer["texture_mask"])
            slots = self.get_active_slots_from_mask(mask)
            all_active_slots.extend(slots)

        return all_active_slots

    def validate_texture_count(self, stage_id: int, texture_count: int) -> tuple[bool, str]:
        """
        Validate that the texture count matches the expected count for a stage.

        Args:
            stage_id: Stage ID (0-21)
            texture_count: Number of textures provided

        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            return False, f"Stage {stage_id} not found in layout database"

        layer_count = layout["layer_count"]
        total_active_slots = 0

        layer_breakdown = []
        for layer in layout["layers"]:
            mask = self.parse_texture_mask(layer["texture_mask"])
            active_slots = self.get_active_slots_from_mask(mask)
            total_active_slots += len(active_slots)
            layer_breakdown.append(f"  Layer {layer['layer_idx']}: {len(active_slots)} active slots")

        if texture_count != total_active_slots:
            msg = f"Texture count mismatch for Stage {stage_id}:\n"
            msg += f"  Expected: {total_active_slots} textures ({layer_count} layer(s))\n"
            msg += f"  Provided: {texture_count} textures\n"
            msg += "\nLayer breakdown:\n"
            msg += "\n".join(layer_breakdown)
            return False, msg

        return True, f"Texture count valid: {texture_count} textures for {layer_count} layer(s)"

    def get_texture_slot_mapping(self, stage_id: int) -> dict[int, list[int]]:
        """
        Get a mapping of layer index to active texture slots.

        Args:
            stage_id: Stage ID (0-21)

        Returns:
            Dictionary mapping layer index to list of active slot indices
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            return {}

        mapping = {}
        for layer in layout["layers"]:
            layer_idx = layer["layer_idx"]
            mask = self.parse_texture_mask(layer["texture_mask"])
            mapping[layer_idx] = self.get_active_slots_from_mask(mask)

        return mapping

    def get_linear_slot_index_map(self, stage_id: int) -> dict[tuple[int, int], int]:
        """
        Get a mapping of (layer_idx, slot_idx) to linear index.
        The linear index corresponds to the sequence in the packed file.
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            return {}

        slot_to_index = {}
        current_idx = 0
        for layer in layout["layers"]:
            l_idx = layer["layer_idx"]
            mask = self.parse_texture_mask(layer["texture_mask"])
            slots = self.get_active_slots_from_mask(mask)
            for slot in slots:
                slot_to_index[(l_idx, slot)] = current_idx
                current_idx += 1
        return slot_to_index

    def get_layer_physics(self, stage_id: int, layer_idx: int) -> dict[str, int]:
        """
        Get physics properties for a specific layer.

        Args:
            stage_id: Stage ID
            layer_idx: Layer index

        Returns:
            Dictionary with speed_x, speed_y, l_limit, r_limit, etc.
            Returns default values if not found.
        """
        defaults = {
            "speed_x": 65536,
            "speed_y": 65536,
            "l_limit": 0,
            "r_limit": 0,
            "y_limit_top": 0,
            "y_limit_bottom": 0,
        }

        stage_data = self._physics.get(str(stage_id))
        if not stage_data:
            return defaults

        layers = stage_data.get("layers", [])
        if layer_idx < len(layers):
            return dict(layers[layer_idx])

        return defaults

    def visualize_mask(self, mask: int, label: str = "Texture Mask") -> str:
        """
        Create a visual ASCII representation of a texture mask.

        Args:
            mask: 32-bit bitmask
            label: Label for the visualization

        Returns:
            Multi-line string with visual representation
        """
        active_slots = self.get_active_slots_from_mask(mask)

        # Create a visual grid (4 rows x 8 columns = 32 slots)
        lines = [f"\n{label}: {hex(mask)}"]
        lines.append("Texture Slot Layout (0-31):")
        lines.append("┌" + "─" * 31 + "┐")

        for row in range(4):
            line = "│"
            for col in range(8):
                slot_idx = row * 8 + col
                if slot_idx in active_slots:
                    line += "███ "
                else:
                    line += "░░░ "
            line = line.rstrip() + "│"
            lines.append(line)

        lines.append("└" + "─" * 31 + "┘")
        lines.append(f"Active slots: {active_slots}")
        lines.append(f"Total active: {len(active_slots)}")

        return "\n".join(lines)

    def print_stage_info(self, stage_id: int) -> None:
        """
        Print detailed information about a stage's layout constraints.

        Args:
            stage_id: Stage ID (0-21)
        """
        layout = self.load_stage_layout(stage_id)
        if not layout:
            print(f"Stage {stage_id} not found in layout database")
            return

        print(f"\n{'=' * 60}")
        print(f"Stage {stage_id:02d} Layout Information")
        print(f"{'=' * 60}")
        print(f"Layer Count: {layout['layer_count']}")
        print()

        total_slots = 0
        for layer in layout["layers"]:
            layer_idx = layer["layer_idx"]
            mask_str = layer["texture_mask"]
            mask = self.parse_texture_mask(mask_str)
            active_slots = self.get_active_slots_from_mask(mask)

            print(f"Layer {layer_idx}:")
            print(f"  Map Name: {layer['map_name']}")
            print(f"  Texture Mask: {mask_str}")
            print(f"  Active Slots: {active_slots}")
            print(f"  Active Count: {len(active_slots)}")
            print(self.visualize_mask(mask, f"  Layer {layer_idx} Mask"))
            print()

            total_slots += len(active_slots)

        print(f"Total Active Texture Slots: {total_slots}")
        print(f"{'=' * 60}\n")


def calculate_active_bounding_box(stage_id: int, db: StageConstraintDB | None = None) -> tuple[int, int]:
    """
    Calculate the bounding box (width, height) that contains all active texture slots.

    Args:
        stage_id: Stage ID (0-21)
        db: Optional StageConstraintDB instance (created if None)

    Returns:
        tuple: (width, height) in pixels, or (1024, 1024) as fallback
    """
    if db is None:
        db = StageConstraintDB()

    layout = db.load_stage_layout(stage_id)
    if not layout:
        return (1024, 1024)  # Fallback to full canvas

    all_active_slots = []
    for layer in layout["layers"]:
        mask = db.parse_texture_mask(layer["texture_mask"])
        slots = db.get_active_slots_from_mask(mask)
        all_active_slots.extend(slots)

    if not all_active_slots:
        return (1024, 1024)

    # Find max row and column from active slots
    # Each slot position: row = slot // 8, col = slot % 8
    max_row = max(slot // 8 for slot in all_active_slots)

    # Calculate bounding box (in pixels, tiles are 128x128)
    height = (max_row + 1) * 128

    # Always use full width (1024) since stages typically span horizontally
    return (1024, height)
