"""Utilities for file hashing and management."""

import hashlib
import os
import struct


def read_pointers(data: bytes) -> list[int]:
    """
    Read pointers from the start of an AFS-like archive.
    The header contains pointers to files/chunks.
    """
    if len(data) < 4:
        return []
    first_offset = struct.unpack("<I", data[0:4])[0]
    if first_offset > len(data) or first_offset < 4:
        return []

    offsets = []
    offset_ptr = 0
    while offset_ptr < first_offset:
        if offset_ptr + 4 > len(data):
            break
        val = struct.unpack("<I", data[offset_ptr : offset_ptr + 4])[0]
        offsets.append(val)
        offset_ptr += 4

    return sorted({o for o in offsets if 0 < o < len(data)})


def get_file_hash(file_path: str, algorithm: str = "md5") -> str | None:
    """
    Calculate hash of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')

    Returns:
        Hash string or None if file doesn't exist/error
    """
    if not os.path.exists(file_path):
        return None

    hash_func = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}.get(algorithm.lower())

    if not hash_func:
        return None

    try:
        hash_obj = hash_func()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (OSError, ValueError):
        return None
