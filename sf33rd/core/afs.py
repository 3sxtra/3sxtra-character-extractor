"""This module provides the AfsArch class for working with AFS archives."""

import logging
import struct


class AfsArch:
    """A class for working with AFS archives.

    This class provides methods for reading, modifying, and writing AFS files.
    AFS is a file archive format used in many Capcom games.

    Attributes:
        files (list): A list of byte strings, where each byte string is the
            content of a file in the archive.
        filenames (list): A list of strings, where each string is the filename
            corresponding to a file in the `files` list.
    """

    def __init__(self) -> None:
        """Initializes the AfsArch object."""
        self.files: list[bytes] = []
        self.filenames: list[str] = []

    def read_from_file(self, afs_path: str) -> None:
        """Reads an AFS file from the given path and populates the `files` and
        `filenames` attributes.

        Args:
            afs_path (str): The path to the AFS file.

        Raises:
            ValueError: If the file is not a valid AFS file.
        """
        with open(afs_path, "rb") as f:
            magic = f.read(4)
            if magic not in (b"AFS\x00", b"AFS "):
                raise ValueError("Not a valid AFS file.")

            num_files = struct.unpack("<I", f.read(4))[0]
            logging.info("Found %d files.", num_files)

            file_table: list[dict[str, int]] = []
            for _ in range(num_files):
                offset, size = struct.unpack("<II", f.read(8))
                file_table.append({"offset": offset, "size": size})

            try:
                attributes_offset, attributes_size = struct.unpack("<II", f.read(8))
            except struct.error:
                attributes_offset, attributes_size = 0, 0

            if attributes_size > 0:
                f.seek(attributes_offset)
                for _ in range(num_files):
                    filename = f.read(32).strip(b"\x00").decode("ascii", errors="ignore")
                    f.read(12)  # Skip timestamp
                    f.read(4)  # Skip custom data
                    self.filenames.append(filename)

            for entry in file_table:
                if entry["size"] == 0:
                    self.files.append(b"")
                    continue

                f.seek(entry["offset"])
                data = f.read(entry["size"])
                self.files.append(data)

    def replace_file(self, index: int, new_filepath: str) -> None:
        """Replaces the file at the given index with a new file.

        Args:
            index (int): The index of the file to replace.
            new_filepath (str): The path to the new file.
        """
        with open(new_filepath, "rb") as f:
            new_data = f.read()
        self.files[index] = new_data
        logging.info("Replaced file at index %d with %s", index, new_filepath)

    def write_to_file(self, afs_path: str) -> None:
        """Writes the modified AFS archive to the given path.

        This method writes the in-memory AFS archive to a file, including the
        header, file table, data, and attributes.

        Args:
            afs_path (str): The path to write the AFS file to.
        """
        num_files = len(self.files)
        # AFS header + file table + attributes pointer
        header_size = 8 + num_files * 8 + 8

        # Align data to 2048 bytes
        data_offset = (header_size + 2047) & -2048

        with open(afs_path, "wb") as f:
            # Write header
            f.write(b"AFS\x00")
            f.write(struct.pack("<I", num_files))

            # Write file table
            current_offset = data_offset
            for data in self.files:
                size = len(data)
                f.write(struct.pack("<II", current_offset, size))
                current_offset += size
                # Align to 2048 bytes
                if current_offset % 2048 != 0:
                    current_offset += 2048 - (current_offset % 2048)

            # Write attributes pointer
            attributes_offset = current_offset
            attributes_size = 0
            if self.filenames:
                attributes_size = num_files * 48
            f.write(struct.pack("<II", attributes_offset, attributes_size))

            # Pad to data_offset
            f.write(b"\x00" * (data_offset - f.tell()))

            # Write file data
            for data in self.files:
                f.write(data)
                # Pad to 2048 bytes
                if f.tell() % 2048 != 0:
                    f.write(b"\x00" * (2048 - (f.tell() % 2048)))

            # Write attributes
            if self.filenames:
                for filename in self.filenames:
                    f.write(filename.encode("ascii").ljust(32, b"\x00"))
                    f.write(b"\x00" * 16)  # Timestamp and custom data
