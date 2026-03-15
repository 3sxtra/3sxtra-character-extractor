"""
Background worker for parsing animation sequences from ROM binary data.

Extracts animation sequences from the game's binary character data files,
including normal animations, effects, and orphaned frame detection.
"""

import logging
import os
import struct
import tempfile

from PyQt6.QtCore import pyqtSignal

from SF3FSPLORERGUI.src.core.workers.base_worker import BaseWorker


def scan_effect_sequences(
    data: bytes, num_of_1st: int, total_frames: int, start_offset: int = 0
) -> list[tuple[list[tuple[int, int]], int]]:
    """Scan binary for 16-byte effect data blocks and group them into sequences.

    Extracted from CharacterExtractorWindow for thread-safe use in workers.
    """
    hits = []
    scan_limit = min(total_frames, 4000)
    scan_start_pos = start_offset

    for local_idx in range(scan_limit):
        gbix = num_of_1st + local_idx
        pattern = struct.pack("<H", gbix) + b"\x00\x00"

        pos = scan_start_pos
        while True:
            pos = data.find(pattern, pos)
            if pos == -1:
                break

            if pos % 2 == 0 and pos + 8 <= len(data):
                val_be = struct.unpack_from(">I", data, pos + 4)[0]
                if val_be <= 255:
                    hits.append((pos, local_idx))
            pos += 1

    if not hits:
        return []

    hits.sort(key=lambda x: x[0])

    sequences: list[tuple[list[tuple[int, int]], int]] = []
    current_seq: list[tuple[int, int]] = []
    last_pos = -100
    current_seq_start_pos = 0

    for pos, local_idx in hits:
        if pos == last_pos + 16:
            duration = 4
            if pos + 8 <= len(data):
                val_be = struct.unpack_from(">I", data, pos + 4)[0]
                val_le = struct.unpack_from("<I", data, pos + 4)[0]
                if 0 < val_be <= 60:
                    duration = val_be
                elif 0 < val_le <= 60:
                    duration = val_le
            current_seq.append((local_idx, duration))
            last_pos = pos
        elif pos > last_pos + 16:
            if current_seq:
                sequences.append((current_seq, current_seq_start_pos))
            current_seq = []
            duration = 4
            if pos + 8 <= len(data):
                val_be = struct.unpack_from(">I", data, pos + 4)[0]
                val_le = struct.unpack_from("<I", data, pos + 4)[0]
                if 0 < val_be <= 60:
                    duration = val_be
                elif 0 < val_le <= 60:
                    duration = val_le
            current_seq.append((local_idx, duration))
            current_seq_start_pos = pos
            last_pos = pos

    if current_seq:
        sequences.append((current_seq, current_seq_start_pos))

    return sequences


# pylint: disable=too-many-locals,too-many-branches,too-many-nested-blocks,too-many-statements
def parse_sequences_from_binary(char_name: str) -> list[dict]:
    """Parse animation sequences from character binary data.

    Thread-safe function that reads character binary files and extracts
    animation sequence data from ROM tables.

    Args:
        char_name: Character name key in character_data

    Returns:
        List of sequence dictionaries with name, frames, start, end, table, index
    """
    logger = logging.getLogger("SequenceParser")
    results: list[dict] = []
    seen_frame_sets: set[tuple] = set()

    try:
        # pylint: disable=import-outside-toplevel
        from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source
        from sf33rd.core.data_model import character_data
        from sf33rd.parsers.animation_parser import AnimationParser
        # pylint: enable=import-outside-toplevel

        data_source = get_afs_data_source()
        char_info = character_data.get(char_name) if character_data else None

        if not char_info or "tex" not in char_info:
            return results

        tex_file = str(char_info["tex"])

        if data_source.source_type == "folder":
            tex_path = data_source.get_file_path(tex_file)
        else:
            tex_data = data_source.get_file_data(str(tex_file))
            temp_dir = tempfile.mkdtemp(prefix="sf33rd_sequences_")
            tex_path = os.path.join(temp_dir, str(tex_file))
            with open(tex_path, "wb") as wf:
                wf.write(tex_data)

        if not tex_path or not os.path.exists(tex_path):
            return results

        with open(tex_path, "rb") as rf:
            data = rf.read()

        # Clean up temp file now that data is in memory
        if data_source.source_type != "folder":
            import shutil  # pylint: disable=import-outside-toplevel

            shutil.rmtree(temp_dir, ignore_errors=True)

        to_chd_value = char_info.get("to_chd", 0)
        header_offset = int(str(to_chd_value)) if to_chd_value else 0
        if header_offset == 0:
            logger.warning(
                "No to_chd offset for %s, cannot parse animations", char_name
            )
            return results

        parser = AnimationParser(data, header_offset_in_file=header_offset)

        num_of_1st = int(char_info.get("num_of_1st", 0))  # type: ignore
        total_frames = struct.unpack_from("<I", data, 0)[0] // 4

        # Parse each animation table
        for table_name in parser.TABLE_NAMES:
            table_desc = parser.TABLE_DESCRIPTIONS.get(table_name, table_name.upper())
            offsets = parser.scan_for_sequences(table_name)

            for seq_idx, offset in enumerate(offsets):
                try:
                    commands = parser.disassemble_script(offset)
                    seq = parser.interpret_sequence(commands)

                    if not seq.frames:
                        continue

                    frame_data: list[tuple[int, int]] = []
                    for frame in seq.frames:
                        local = frame.sprite_index - num_of_1st
                        if 0 <= local < total_frames:
                            frame_data.append((local, frame.duration))

                    if not frame_data or len(frame_data) >= 100 or len(frame_data) < 2:
                        continue

                    frame_key = tuple(frame_data)
                    if frame_key in seen_frame_sets:
                        continue
                    seen_frame_sets.add(frame_key)

                    seq_name = (
                        f"{table_desc} #{seq_idx + 1:03d} ({len(frame_data)}f)"
                    )
                    results.append(
                        {
                            "name": seq_name,
                            "frames": frame_data,
                            "start": frame_data[0][0],
                            "end": frame_data[-1][0],
                            "table": table_name,
                            "index": seq_idx,
                        }
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    continue

        # Parse effect animations from ovct table
        try:
            effect_sequences = parser.get_effect_sequences()

            for eff_seq in effect_sequences:
                if not eff_seq.frames:
                    continue

                effect_frame_data: list[tuple[int, int]] = []
                for frame in eff_seq.frames:
                    local = frame.sprite_index - num_of_1st
                    if 0 <= local < total_frames:
                        effect_frame_data.append((local, frame.duration))

                if (
                    not effect_frame_data
                    or len(effect_frame_data) < 2
                    or len(effect_frame_data) >= 100
                ):
                    continue

                frame_key = tuple(effect_frame_data)
                if frame_key in seen_frame_sets:
                    continue
                seen_frame_sets.add(frame_key)

                seq_name = f"{eff_seq.name} ({len(effect_frame_data)}f)"
                results.append(
                    {
                        "name": seq_name,
                        "frames": effect_frame_data,
                        "start": effect_frame_data[0][0],
                        "end": effect_frame_data[-1][0],
                        "table": "effects",
                        "index": len(results),
                    }
                )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Could not parse effect sequences")

        # Heuristic scan for data-block effects
        try:
            used_frames = set()
            for result_seq in results:
                result_frames = result_seq.get("frames", [])
                if isinstance(result_frames, list):
                    for f_idx, _ in result_frames:
                        used_frames.add(f_idx)

            to_chd_val = char_info.get("to_chd", 0)
            to_chd = int(str(to_chd_val)) if to_chd_val else 0
            scanned_effects = scan_effect_sequences(
                data, num_of_1st, total_frames, start_offset=to_chd
            )

            for i, (frames, offset) in enumerate(scanned_effects):
                if len(frames) < 2:
                    continue
                seq_frame_indices = set(f[0] for f in frames)
                if seq_frame_indices.issubset(used_frames):
                    continue
                overlap = seq_frame_indices.intersection(used_frames)
                if len(overlap) > len(seq_frame_indices) * 0.8:
                    continue

                seq_name = (
                    f"Effect Data #{i + 1:03d} (0x{offset:X}) ({len(frames)}f)"
                )
                results.append(
                    {
                        "name": seq_name,
                        "frames": frames,
                        "start": frames[0][0],
                        "end": frames[-1][0],
                        "table": "effect_data",
                        "index": i,
                    }
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Effect scan failed: %s", e)

        # Identify orphaned frames
        try:
            final_usage = set()
            for result_seq in results:
                result_frames = result_seq.get("frames", [])
                if isinstance(result_frames, list):
                    for f_idx, _ in result_frames:
                        final_usage.add(f_idx)

            all_frames_set = set(range(total_frames))
            orphans = sorted(list(all_frames_set - final_usage))

            if orphans:
                orphan_ranges: list[list[int]] = []
                current_range = [orphans[0]]
                prev = orphans[0]
                for x in orphans[1:]:
                    if x == prev + 1:
                        current_range.append(x)
                    else:
                        orphan_ranges.append(current_range)
                        current_range = [x]
                    prev = x
                orphan_ranges.append(current_range)

                for i, rng in enumerate(orphan_ranges):
                    if len(rng) < 2:
                        continue
                    frames = [(fx, 4) for fx in rng]
                    seq_name = (
                        f"Orphan Data #{i + 1:03d} (Frames {rng[0]}-{rng[-1]})"
                    )
                    results.append(
                        {
                            "name": seq_name,
                            "frames": frames,
                            "start": rng[0],
                            "end": rng[-1],
                            "table": "orphans",
                            "index": i,
                        }
                    )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Orphan scan failed: %s", e)

        logger.info(
            "Parsed %d unique sequences from ROM tables for %s",
            len(results),
            char_name,
        )
        return results

    except ImportError:
        logger.error("Could not import sf33rd tools for binary parsing.")
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error parsing binary sequences: %s", e)
        return results


class SequenceParseWorker(BaseWorker):
    """Background worker for parsing animation sequences from ROM binary data."""

    sequences_parsed = pyqtSignal(list)  # list of sequence dicts

    def __init__(self):
        super().__init__()
        self._char_name = ""
        self.set_timeout(60)

    def set_params(self, char_name: str) -> None:
        """Set the character name to parse sequences for."""
        self._char_name = char_name

    def _do_work(self):
        """Parse sequences from binary data."""
        results = parse_sequences_from_binary(self._char_name)
        if results:
            self.sequences_parsed.emit(results)
        return results
