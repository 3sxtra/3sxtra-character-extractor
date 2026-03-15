"""
Compatibility utilities for SF3:3rd Asset Explorer.
Handles conditional importing of the core sf33rd library.
"""

import importlib.util
import logging
import sys

# Try to ensure project root is in path
try:
    from SF3FSPLORERGUI.src.utils.helpers import get_project_root

    project_root = get_project_root()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except ImportError:
    pass

logger = logging.getLogger(__name__)

try:
    spec = importlib.util.find_spec("sf33rd")
    if spec is None:
        # Fallback: try direct import as find_spec can be finicky
        try:
            import sf33rd  # noqa: F401 # pylint: disable=unused-import

            SF33RD_AVAILABLE = True
        except ImportError:
            logger.warning("sf33rd package not found via find_spec or import.")
            SF33RD_AVAILABLE = False
    else:
        SF33RD_AVAILABLE = True

    if SF33RD_AVAILABLE:
        # Try to load character data
        try:
            from sf33rd.core.data_model import character_data

            CHARACTERS = sorted(character_data.keys())
        except ImportError as e:
            logger.error("Failed to import character_data from sf33rd: %s", e)
            CHARACTERS = ["Ryu", "Ken", "Alex", "Chun-Li"]

except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Error checking compatibility: %s", e)
    SF33RD_AVAILABLE = False
    CHARACTERS = ["Ryu", "Ken", "Alex", "Chun-Li"]

if not SF33RD_AVAILABLE:
    logger.warning("sf33rd library not found. Operations will be simulated.")
