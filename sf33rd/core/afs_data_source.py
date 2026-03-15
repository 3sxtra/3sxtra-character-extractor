"""
AFS Data Source abstraction for unified access to game assets.

This module provides a unified interface for accessing SF33RD game assets
from either:
1. An AFS archive file (SF33RD.AFS)
2. An extracted folder (afsextracted/)

Priority order for auto-discovery:
1. {user_data}/CrowdedStreet/3SX/resources/SF33RD.AFS
2. {app_root}/SF33RD.AFS
3. {user_data}/CrowdedStreet/3SX/resources/afsextracted/
4. {app_root}/afsextracted/

Where {user_data} is:
- Windows: %APPDATA%
- macOS: ~/Library/Application Support
- Linux: ~/.local/share
"""

from __future__ import annotations

import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cached singleton instance (mutable module state, not a true constant)
_cached_data_source: AfsDataSource | None = None  # pylint: disable=invalid-name


def _get_user_data_dir() -> str:
    """Get the platform-appropriate user data directory.

    Returns:
        - Windows: %APPDATA%
        - macOS: ~/Library/Application Support
        - Linux: ~/.local/share
    """
    if sys.platform == "win32":
        # Windows: use APPDATA
        return os.environ.get("APPDATA", os.path.expanduser("~"))
    if sys.platform == "darwin":
        # macOS: use ~/Library/Application Support
        return os.path.expanduser("~/Library/Application Support")
    # Linux/Unix: use ~/.local/share (XDG_DATA_HOME fallback)
    return os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))


class AfsDataSource(ABC):
    """Abstract base class for AFS data access."""

    source_type: Literal["archive", "folder"]
    source_path: str

    @abstractmethod
    def get_file_data(self, filename: str) -> bytes:
        """
        Read file data by name.

        Args:
            filename: Name of the file (e.g., 'pl02.bin')

        Returns:
            Raw bytes of the file content.

        Raises:
            FileNotFoundError: If file doesn't exist in source.
        """

    @abstractmethod
    def file_exists(self, filename: str) -> bool:
        """
        Check if file exists in source.

        Args:
            filename: Name of the file to check.

        Returns:
            True if file exists, False otherwise.
        """

    @abstractmethod
    def list_files(self) -> list[str]:
        """
        List all files in the data source.

        Returns:
            List of filenames.
        """

    def get_file_path(self, filename: str) -> str | None:
        """
        Get file path if source is a folder.

        For archive sources, returns None (use get_file_data instead).

        Args:
            filename: Name of the file.

        Returns:
            Absolute path to file if folder source, None if archive.
        """
        if self.source_type == "folder":
            return os.path.join(self.source_path, filename)
        return None

    @classmethod
    def auto_discover(cls) -> AfsDataSource:
        """
        Find best available AFS data source using priority order.

        Priority:
            1. {user_data}/CrowdedStreet/3SX/resources/SF33RD.AFS
            2. {cwd}/SF33RD.AFS
            3. {user_data}/CrowdedStreet/3SX/resources/afsextracted/
            4. {cwd}/afsextracted/

        Returns:
            AfsDataSource instance.

        Raises:
            FileNotFoundError: If no valid source found.
        """
        global _cached_data_source  # pylint: disable=global-statement
        if _cached_data_source is not None:
            return _cached_data_source

        # Get user resources directory (platform-specific)
        user_data = _get_user_data_dir()
        user_resources = os.path.join(user_data, "CrowdedStreet", "3SX", "resources")
        cwd = os.getcwd()

        # Priority 1: User data SF33RD.AFS
        user_afs = os.path.join(user_resources, "SF33RD.AFS")
        if os.path.isfile(user_afs):
            logger.info("Using AFS archive: %s", user_afs)
            _cached_data_source = ArchiveDataSource(user_afs)
            return _cached_data_source

        # Priority 2: CWD SF33RD.AFS
        cwd_afs = os.path.join(cwd, "SF33RD.AFS")
        if os.path.isfile(cwd_afs):
            logger.info("Using AFS archive: %s", cwd_afs)
            _cached_data_source = ArchiveDataSource(cwd_afs)
            return _cached_data_source

        # Priority 3: User data afsextracted
        user_extracted = os.path.join(user_resources, "afsextracted")
        if os.path.isdir(user_extracted):
            logger.info("Using extracted folder: %s", user_extracted)
            _cached_data_source = FolderDataSource(user_extracted)
            return _cached_data_source

        # Priority 4: CWD afsextracted
        cwd_extracted = os.path.join(cwd, "afsextracted")
        if os.path.isdir(cwd_extracted):
            logger.info("Using extracted folder: %s", cwd_extracted)
            _cached_data_source = FolderDataSource(cwd_extracted)
            return _cached_data_source

        raise FileNotFoundError(
            f"No AFS data source found. Searched:\n"
            f"  1. {user_afs}\n"
            f"  2. {cwd_afs}\n"
            f"  3. {user_extracted}\n"
            f"  4. {cwd_extracted}"
        )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached data source singleton."""
        global _cached_data_source  # pylint: disable=global-statement
        _cached_data_source = None


class FolderDataSource(AfsDataSource):
    """Data source for extracted folder (afsextracted/)."""

    source_type: Literal["archive", "folder"] = "folder"

    def __init__(self, folder_path: str) -> None:
        """
        Initialize folder data source.

        Args:
            folder_path: Path to extracted folder.
        """
        self.source_path = os.path.abspath(folder_path)
        if not os.path.isdir(self.source_path):
            raise FileNotFoundError(f"Folder not found: {self.source_path}")

    def get_file_data(self, filename: str) -> bytes:
        """Read file from folder."""
        filepath = os.path.join(self.source_path, filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, "rb") as f:
            return f.read()

    def file_exists(self, filename: str) -> bool:
        """Check if file exists in folder."""
        return os.path.isfile(os.path.join(self.source_path, filename))

    def list_files(self) -> list[str]:
        """List all files in folder."""
        return [f for f in os.listdir(self.source_path) if os.path.isfile(os.path.join(self.source_path, f))]


class ArchiveDataSource(AfsDataSource):
    """Data source for AFS archive file (SF33RD.AFS)."""

    source_type: Literal["archive", "folder"] = "archive"

    def __init__(self, archive_path: str) -> None:
        """
        Initialize archive data source.

        Args:
            archive_path: Path to AFS archive file.
        """
        from sf33rd.core.afs import AfsArch  # pylint: disable=import-outside-toplevel

        self.source_path = os.path.abspath(archive_path)
        if not os.path.isfile(self.source_path):
            raise FileNotFoundError(f"Archive not found: {self.source_path}")

        self._archive = AfsArch()
        self._archive.read_from_file(self.source_path)

        # Build filename -> index lookup
        self._file_index: dict[str, int] = {}
        for idx, name in enumerate(self._archive.filenames):
            self._file_index[name.lower()] = idx

        logger.info("Loaded AFS archive with %d files", len(self._archive.files))

    def get_file_data(self, filename: str) -> bytes:
        """Read file from archive."""
        idx = self._file_index.get(filename.lower())
        if idx is None:
            raise FileNotFoundError(f"File not found in archive: {filename}")
        return self._archive.files[idx]

    def file_exists(self, filename: str) -> bool:
        """Check if file exists in archive."""
        return filename.lower() in self._file_index

    def list_files(self) -> list[str]:
        """List all files in archive."""
        return list(self._archive.filenames)
