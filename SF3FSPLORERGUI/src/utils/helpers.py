#!/usr/bin/env python3
"""
General utility functions
"""

try:
    from sf33rd.constants import (
        SUPPORTED_ARCHIVE_EXTENSIONS,
        SUPPORTED_AUDIO_EXTENSIONS,
        SUPPORTED_IMAGE_EXTENSIONS,
    )
    from sf33rd.utils.file_utils import get_file_hash
except ImportError:
    get_file_hash = None  # type: ignore


import os
from collections.abc import Callable
from pathlib import Path
from typing import Any


def format_file_size(size_bytes: int | float) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: File size in bytes

    Returns:
        Human-readable file size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0

    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename

    Args:
        filename: Name of the file

    Returns:
        File extension with dot (e.g., '.txt')
    """
    if not filename or "." not in filename:
        return ""

    return Path(filename).suffix.lower()


def is_audio_file(filename: str) -> bool:
    """
    Check if file is an audio file

    Args:
        filename: Name of the file

    Returns:
        True if audio file, False otherwise
    """
    return get_file_extension(filename) in SUPPORTED_AUDIO_EXTENSIONS


def is_image_file(filename: str) -> bool:
    """
    Check if file is an image file

    Args:
        filename: Name of the file

    Returns:
        True if image file, False otherwise
    """
    return get_file_extension(filename) in SUPPORTED_IMAGE_EXTENSIONS


def is_archive_file(filename: str) -> bool:
    """
    Check if file is an archive file

    Args:
        filename: Name of the file

    Returns:
        True if archive file, False otherwise
    """
    return get_file_extension(filename) in SUPPORTED_ARCHIVE_EXTENSIONS


def create_progress_callback(progress_signal: Any | None = None) -> Callable:
    """
    Create a progress callback function

    Args:
        progress_signal: Signal to emit progress updates

    Returns:
        Progress callback function
    """

    def progress_callback(current: int, maximum: int):
        """Progress callback function"""
        if progress_signal:
            progress_signal.emit(current, maximum)

    return progress_callback


def format_duration(seconds: int | float) -> str:
    """
    Format duration in seconds to human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (MM:SS or HHH:MM:SS)
    """
    if seconds < 0:
        return "00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_directory(path: str) -> bool:
    """
    Create directory if it doesn't exist

    Args:
        path: Directory path to create

    Returns:
        True if directory was created or already exists, False otherwise
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Remove invalid characters for Windows, macOS, and Linux
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join(c for c in filename if c not in invalid_chars)

    # Remove trailing dots and spaces
    sanitized = sanitized.rstrip(". ")

    # Ensure filename is not empty
    if not sanitized:
        sanitized = "untitled"

    return sanitized


def get_mime_type(file_path: str) -> str | None:
    """
    Get MIME type from file extension

    Args:
        file_path: Path to the file

    Returns:
        MIME type string or None if unknown
    """
    extension = get_file_extension(file_path)

    mime_types = {
        ".adx": "audio/adx",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
    }

    return mime_types.get(extension)


def get_user_resources_directory() -> str:
    """
    Get the CrowdedStreet 3SX user resources directory (cross-platform).

    Returns:
        Path to the user resources directory:
        - Windows: %APPDATA%/CrowdedStreet/3SX/resources
        - macOS:   ~/Library/Application Support/CrowdedStreet/3SX/resources
        - Linux:   ~/.local/share/CrowdedStreet/3SX/resources
    """
    import sys  # pylint: disable=import-outside-toplevel

    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    return os.path.join(base, "CrowdedStreet", "3SX", "resources")


def get_afs_archive_path() -> str | None:
    """
    Find SF33RD.AFS with priority.

    Priority:
        1. {AppData}/CrowdedStreet/3SX/resources/SF33RD.AFS
        2. {project_root}/SF33RD.AFS
        3. ./SF33RD.AFS

    Returns:
        Path to SF33RD.AFS if found, None otherwise.
    """
    # Priority 1: User resources directory
    user_afs = os.path.join(get_user_resources_directory(), "SF33RD.AFS")
    if os.path.exists(user_afs):
        return user_afs

    # Priority 2: Project root
    root_afs = os.path.join(get_project_root(), "SF33RD.AFS")
    if os.path.exists(root_afs):
        return root_afs

    # Priority 3: Current directory
    if os.path.exists("SF33RD.AFS"):
        return "SF33RD.AFS"

    return None


def get_afs_data_source():
    """
    Get the unified AFS data source for accessing game assets.

    This function provides a unified interface for reading game assets
    from either SF33RD.AFS archive or an extracted afsextracted/ folder.

    Priority:
        1. {AppData}/CrowdedStreet/3SX/resources/SF33RD.AFS
        2. {cwd}/SF33RD.AFS
        3. {AppData}/CrowdedStreet/3SX/resources/afsextracted/
        4. {cwd}/afsextracted/

    Returns:
        AfsDataSource: Data source instance for reading game files.

    Raises:
        FileNotFoundError: If no valid source found.

    Example:
        >>> source = get_afs_data_source()
        >>> data = source.get_file_data("pl02.bin")
        >>> if source.source_type == "folder":
        ...     path = source.get_file_path("pl02.bin")
    """
    # Import here to avoid circular imports
    # pylint: disable=import-outside-toplevel
    from sf33rd.core.afs_data_source import AfsDataSource

    return AfsDataSource.auto_discover()


def get_afs_directory(game_root: str) -> str:
    """
    Resolve AFS extracted directory path.

    Priority:
        1. {AppData}/CrowdedStreet/3SX/resources/afsextracted
        2. game_root/afsextracted
        3. ./afsextracted

    Args:
        game_root: Path to game root directory

    Returns:
        Path to afsextracted directory.

    Raises:
        FileNotFoundError: If directory is not found.
    """
    # Priority 1: User resources directory
    user_afs_dir = os.path.join(get_user_resources_directory(), "afsextracted")
    if os.path.exists(user_afs_dir):
        return user_afs_dir

    # Priority 2: Game root
    game_afs_dir = os.path.join(game_root, "afsextracted")
    if os.path.exists(game_afs_dir):
        return game_afs_dir

    # Priority 3: Local fallback
    if os.path.exists("afsextracted"):
        return "afsextracted"

    raise FileNotFoundError(
        f"AFS directory not found. Searched:\n  1. {user_afs_dir}\n  2. {game_afs_dir}\n  3. ./afsextracted"
    )


def calculate_hash(file_path: str, algorithm: str = "md5") -> str | None:
    """
    Calculate hash of a file.
    Delegates to sf33rd.utils.file_utils.get_file_hash.
    """
    if callable(get_file_hash):
        return get_file_hash(file_path, algorithm)
    return None


def get_project_root() -> str:
    """
    Get the project root directory.
    Tries to find the root by looking for 'sf33rd' package or '.git' directory.
    Fallback to current working directory.

    Returns:
        Absolute path to the project root.
    """
    import logging  # pylint: disable=import-outside-toplevel

    logger = logging.getLogger(__name__)

    # Start from this file's directory
    current_path = Path(__file__).resolve().parent

    # Traverse up
    while current_path != current_path.parent:
        if (current_path / "sf33rd").exists() and (current_path / "sf33rd").is_dir():
            logger.info("Project root found (sf33rd): %s", current_path)
            return str(current_path)
        if (current_path / ".git").exists():
            logger.info("Project root found (.git): %s", current_path)
            return str(current_path)
        current_path = current_path.parent

    # If not found, assume we are running from root or use cwd
    cwd = os.getcwd()
    logger.warning("Project root not found, using CWD: %s", cwd)
    return cwd
