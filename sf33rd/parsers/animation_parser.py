"""Animation parser for SF3:3rd Strike character animation tables."""

import struct
from dataclasses import dataclass, field


@dataclass
class Frame:
    """Represents a single animation frame."""

    sprite_index: int = 0
    duration: int = 1
    offset_x: int = 0
    offset_y: int = 0
    flags: int = 0
    olc_ix: int = 0  # Index into ovct table for effect palette lookup


@dataclass
class Command:
    """Represents a parsed animation command."""

    opcode: int
    koc: int
    ix: int
    pat: int
    offset: int
    name: str = ""
    olc_ix: int = 0  # cg_olc_ix from animation data


@dataclass
class Sequence:
    """Represents a sequence of animation frames."""

    name: str = ""
    frames: list[Frame] = field(default_factory=list)
    start_offset: int = 0


@dataclass
class EffectPart:
    """Represents an effect overlay part (UNK_8 from game source).

    Used for smoke, fireballs, super art effects, etc.
    These use the same sprite atlas as the character.
    """

    sprite_index: int = 0  # parts_char - GBIX of sprite to display
    duration: int = 1  # parts_timer - Duration in ticks
    offset_x: int = 0  # parts_hos_x - X offset from character
    offset_y: int = 0  # parts_hos_y - Y offset from character
    next_index: int = 0  # parts_nix - Next effect index (for chaining)
    flip: int = 0  # parts_flip - Flip flags
    priority: int = 0  # parts_prio - Z priority
    display_mode: int = 0  # parts_disp - Display mode


class AnimationParser:
    """Parses character animation tables and scripts."""

    # Table names in CharInitData struct order (from structs.h lines 1185-1194):
    # char_init_data->nmca = index 0
    # char_init_data->dmca = index 1
    # char_init_data->btca = index 2  (Battle, NOT caca!)
    # char_init_data->caca = index 3
    # char_init_data->cuca = index 4
    # char_init_data->atca = index 5
    # char_init_data->saca = index 6
    # char_init_data->exca = index 7
    # char_init_data->cbca = index 8
    # char_init_data->yuca = index 9
    TABLE_NAMES = ["nmca", "dmca", "btca", "caca", "cuca", "atca", "saca", "exca", "cbca", "yuca"]

    # Human-readable descriptions for each table (from game source)
    TABLE_DESCRIPTIONS = {
        "nmca": "Normal",  # NormalOperation
        "dmca": "Damage",  # ClientBehavior1
        "btca": "Battle",  # ClientBehavior2
        "caca": "Throws",  # Throws
        "cuca": "Caught",  # ClientBehavior3
        "atca": "Tricks",  # Tricks
        "saca": "Supers",  # Mortals
        "exca": "Landing",  # LandingBehavior
        "cbca": "Subroutine",  # SubroutineMortal
        "yuca": "Victory",  # VictoryPose
    }

    # CharInitData additional table indices (after animation tables)
    # stxy=10, mvxy=11, sernd=12, ovct=13, ovix=14
    OVCT_INDEX = 13  # Effect overlay table
    EFFECT_ENTRY_SIZE = 16  # sizeof(UNK_8) = 16 bytes

    OPCODES = {
        0x00: "comm_dummy",
        0x01: "comm_roa",
        0x02: "comm_end",
        0x03: "comm_jmp",
        0x04: "comm_jpss",
        0x05: "comm_jsr",
        0x06: "comm_ret",
        0x07: "comm_sps",
        0x08: "comm_setr",
        0x09: "comm_addr",
        0x0A: "comm_if_l",
        0x0B: "comm_djmp",
        0x0C: "comm_for",
        0x0D: "comm_nex",
        0x0E: "comm_for2",
        0x0F: "comm_nex2",
        0x10: "comm_rja",
        0x11: "comm_uja",
        0x12: "comm_rja2",
        0x13: "comm_uja2",
        0x14: "comm_rja3",
        0x15: "comm_uja3",
        0x16: "comm_rja4",
        0x17: "comm_uja4",
        0x18: "comm_rja5",
        0x19: "comm_uja5",
        0x1A: "comm_rja6",
        0x1B: "comm_uja6",
        0x1C: "comm_rja7",
        0x1D: "comm_uja7",
        0x1E: "comm_rmja",
        0x1F: "comm_umja",
        0x20: "comm_rmja2",
        0x21: "comm_umja2",
        0x22: "comm_rmja3",
        0x23: "comm_umja3",
        0x24: "comm_rmja4",
        0x25: "comm_umja4",
        0x26: "comm_ps_x",
        0x27: "comm_ps_y",
        0x28: "comm_ps_xy",
        0x29: "comm_ps_a_x",
        0x2A: "comm_ps_a_y",
        0x2B: "comm_ps_a_xy",
        0x2C: "comm_ps_v_x",
        0x2D: "comm_ps_v_y",
        0x2E: "comm_ps_v_xy",
        0x2F: "comm_ps_va_x",
        0x30: "comm_ps_va_y",
        0x31: "comm_ps_va_xy",
        0x32: "comm_set_fl",
        0x33: "comm_clr_fl",
        0x34: "comm_bit_fl",
        0x35: "comm_set_vh",
        0x36: "comm_set_vha",
        0x37: "comm_set_vhs",
        0x38: "comm_set_vhsa",
        0x7C: "comm_hitbox",
    }

    def __init__(self, data: bytes, header_offset_in_file: int = 0):
        self.data = data
        self.header_offset = header_offset_in_file
        self.tables: dict[str, int] = {}
        self.endian = "<"  # Default
        self.detect_endianness()
        self.parse_header()

    def detect_endianness(self):
        """Checks the first table offset to determine endianness."""
        # Find the first non-zero offset in the header to check endianness
        num_tables = len(self.TABLE_NAMES)
        for i in range(num_tables):
            off = self.header_offset + (i * 4)
            if off + 4 > len(self.data):
                break
            le_val = struct.unpack_from("<I", self.data, off)[0] & 0x3FFFFF
            be_val = struct.unpack_from(">I", self.data, off)[0] & 0x3FFFFF

            if le_val != 0 and le_val < 100000:
                self.endian = "<"
                return
            if be_val != 0 and be_val < 100000:
                self.endian = ">"
                return
        self.endian = "<"  # Default fallback

    def parse_header(self) -> None:
        """Parse the animation table header to extract table offsets."""
        if not self.data:
            return
        # Only parse as many tables as we have names for
        num_tables = len(self.TABLE_NAMES)
        max_entries = min(num_tables, (len(self.data) - self.header_offset) // 4)
        for i in range(max_entries):
            rel_off = struct.unpack_from(f"{self.endian}I", self.data, self.header_offset + (i * 4))[0]
            rel_off &= 0x3FFFFF
            if rel_off != 0 and rel_off < len(self.data):
                self.tables[self.TABLE_NAMES[i]] = self.header_offset + rel_off

    def get_script_offsets(self, table_name: str) -> list[int]:
        """Get offsets to animation scripts within a table.

        Each animation table (nmca, dmca, etc.) starts with a list of 4-byte offsets.
        These offsets are relative to the TABLE start (not the header!), and point
        to actual animation script commands.
        """
        if table_name not in self.tables:
            return []
        table_start = self.tables[table_name]

        offsets = []
        current = table_start
        # Tables are lists of 4-byte pointers, ending in 0x00000000
        for _ in range(500):  # Safety limit
            if current + 4 > len(self.data):
                break
            val = struct.unpack_from(f"{self.endian}I", self.data, current)[0]
            if val == 0:
                break

            # Offsets are relative to the TABLE start, not header
            script_abs_offset = table_start + val
            if script_abs_offset < len(self.data):
                offsets.append(script_abs_offset)
            current += 4
        return offsets

    def scan_for_sequences(self, table_name: str) -> list[int]:
        """Scan for animation sequences in the specified table."""
        return self.get_script_offsets(table_name)

    def get_auto_sequences(self) -> list[int]:
        """Provides fallback sequence discovery for missing tables."""
        offsets = []
        # Scan for comm_end (0x02) markers as a heuristic for script ends
        for i in range(0, len(self.data) - 8, 4):
            # Check for Big Endian end marker
            if self.data[i : i + 2] == b"\x00\x02":
                offsets.append(max(0, i - 16))
            # Check for Little Endian end marker
            if self.data[i : i + 2] == b"\x02\x00":
                offsets.append(max(0, i - 16))
        return sorted(list(set(offsets)))

    def disassemble_script(self, offset: int, max_commands: int = 100) -> list[Command]:
        """Disassemble animation script starting at offset.

        Animation scripts use the UNK11 structure (8 bytes per entry):
        - u16 code:  Low byte = flags, high byte = DURATION (cg_ctr in game)
        - s16 koc:   Parameter (command argument or frame metadata)
        - s16 ix:    X offset / parameter
        - s16 pat:   Sprite GBIX (if > 256) or parameter

        The game's WORK struct maps the first u32 as:
          u8 cg_type = code & 0xFF
          u8 cg_ctr = (code >> 8) & 0xFF  ← This is the DURATION!
          u16 cg_se = next 2 bytes

        Frame entries: pat > 256 indicates valid sprite GBIX.
        Script stops at flow control commands (code & 0xFF in {1,2,3,4,6}).
        """
        flow_control_opcodes = {0x01, 0x02, 0x03, 0x04, 0x06}

        commands = []
        current = offset
        entry_size = 8  # UNK11 is 8 bytes

        for _ in range(max_commands):
            if current + entry_size > len(self.data):
                break

            # Parse UNK11 struct: u16 code, s16 koc, s16 ix, s16 pat
            code = struct.unpack_from("<H", self.data, current)[0]  # u16
            koc = struct.unpack_from("<h", self.data, current + 2)[0]  # s16 (signed!)
            ix = struct.unpack_from("<h", self.data, current + 4)[0]  # s16
            pat = struct.unpack_from("<h", self.data, current + 6)[0]  # s16

            # Duration is in high byte of code field (game's cg_ctr)
            opcode_byte = code & 0xFF
            duration = (code >> 8) & 0xFF

            # Frame detection: pat field contains sprite GBIX if > 256
            if pat > 256:
                # This entry has a valid sprite GBIX in pat field
                cmd = Command(
                    opcode=0,  # Mark as frame entry
                    koc=duration,  # Duration from high byte of code!
                    ix=ix,
                    pat=pat,  # Sprite GBIX from pat field
                    offset=current,
                    name=f"FRAME_{pat}",
                    olc_ix=0,
                )
            elif opcode_byte < 0x80:
                # This is a command entry (low opcode values)
                cmd = Command(
                    opcode=opcode_byte,
                    koc=koc,
                    ix=ix,
                    pat=pat,
                    offset=current,
                    name=self.OPCODES.get(opcode_byte, f"CMD_{opcode_byte:02X}"),
                    olc_ix=0,
                )
            else:
                # Other data entry (high opcode_byte but pat <= 256)
                cmd = Command(
                    opcode=opcode_byte,
                    koc=duration,  # Store duration for potential use
                    ix=ix,
                    pat=pat,
                    offset=current,
                    name=f"DATA_{code:04X}",
                    olc_ix=0,
                )

            commands.append(cmd)
            current += entry_size

            # Stop at flow control commands
            if opcode_byte in flow_control_opcodes and pat <= 256:
                break

        return commands

    def interpret_sequence(self, commands: list[Command]) -> Sequence:
        """Extract frames from a disassembled command sequence.

        After disassemble_script:
        - Frame entries have: opcode=0, pat=sprite GBIX, koc=duration
        - Duration is from high byte of code field (game's cg_ctr)
        - Frames with duration <= 0 or > 60 are filtered as invalid
        """
        seq = Sequence()
        if not commands:
            return seq
        seq.start_offset = commands[0].offset

        for cmd in commands:
            # Frame entry: pat > 256 (valid sprite GBIX) and opcode == 0
            if cmd.pat > 256 and cmd.opcode == 0:
                # Duration is now stored in cmd.koc by disassemble_script
                # Filter out frames with invalid durations (parsing errors)
                if cmd.koc < 1 or cmd.koc > 60:
                    continue

                frame = Frame(
                    sprite_index=cmd.pat,
                    duration=cmd.koc,
                    flags=0,
                    olc_ix=cmd.olc_ix,
                )
                seq.frames.append(frame)

        return seq

    def get_ovct_offset(self) -> int:
        """Get the absolute offset to the ovct (effect overlay) table."""
        if self.header_offset + (self.OVCT_INDEX * 4) + 4 > len(self.data):
            return 0
        rel_off = struct.unpack_from(f"{self.endian}I", self.data, self.header_offset + (self.OVCT_INDEX * 4))[0]
        rel_off &= 0x3FFFFF
        if rel_off == 0:
            return 0
        return int(self.header_offset + rel_off)

    def parse_effect_entry(self, offset: int) -> EffectPart:
        """Parse a single UNK_8 effect entry at the given offset.

        UNK_8 structure (16 bytes):
        - s16 parts_hos_x;       // X offset
        - s16 parts_hos_y;       // Y offset
        - u8 parts_colmd;        // Color mode
        - u8 parts_colcd;        // Color code
        - u8 parts_prio;         // Priority
        - u8 parts_flip;         // Flip flags
        - u8 parts_timer;        // Duration
        - u8 parts_disp;         // Display mode
        - s16 parts_mts;
        - u16 parts_nix;         // Next index
        - u16 parts_char;        // Sprite GBIX
        """
        if offset + self.EFFECT_ENTRY_SIZE > len(self.data):
            return EffectPart()

        parts_hos_x = struct.unpack_from(f"{self.endian}h", self.data, offset)[0]
        parts_hos_y = struct.unpack_from(f"{self.endian}h", self.data, offset + 2)[0]
        # Skip colmd, colcd (bytes 4-5)
        parts_prio = self.data[offset + 6]
        parts_flip = self.data[offset + 7]
        parts_timer = self.data[offset + 8]
        parts_disp = self.data[offset + 9]
        # Skip parts_mts (bytes 10-11)
        parts_nix = struct.unpack_from(f"{self.endian}H", self.data, offset + 12)[0]
        parts_char = struct.unpack_from(f"{self.endian}H", self.data, offset + 14)[0]

        return EffectPart(
            sprite_index=parts_char,
            duration=max(1, parts_timer) if parts_timer > 0 else 1,
            offset_x=parts_hos_x,
            offset_y=parts_hos_y,
            next_index=parts_nix,
            flip=parts_flip,
            priority=parts_prio,
            display_mode=parts_disp,
        )

    def get_effect_sequences(self, max_effects: int = 200) -> list[Sequence]:
        """Parse effect animations from the ovct table.

        Returns a list of Sequences, each containing effect frames.
        Effect chains are followed via parts_nix until loop or end.
        """
        ovct_offset = self.get_ovct_offset()
        if ovct_offset == 0:
            return []

        sequences = []
        visited = set()  # Track visited indices to detect loops

        for start_idx in range(max_effects):
            entry_offset = ovct_offset + (start_idx * self.EFFECT_ENTRY_SIZE)
            if entry_offset + self.EFFECT_ENTRY_SIZE > len(self.data):
                break

            effect = self.parse_effect_entry(entry_offset)

            # Skip empty entries (no sprite)
            if effect.sprite_index == 0:
                continue

            # Skip if we've already included this as part of another chain
            if start_idx in visited:
                continue

            # Build a sequence from this effect chain
            seq = Sequence(name=f"Effect #{start_idx + 1}", start_offset=entry_offset)

            current_idx = start_idx
            chain_visited = set()

            while current_idx not in chain_visited:
                chain_visited.add(current_idx)
                visited.add(current_idx)

                eff_offset = ovct_offset + (current_idx * self.EFFECT_ENTRY_SIZE)
                if eff_offset + self.EFFECT_ENTRY_SIZE > len(self.data):
                    break

                eff = self.parse_effect_entry(eff_offset)
                if eff.sprite_index == 0:
                    break

                # Add as frame
                frame = Frame(
                    sprite_index=eff.sprite_index,
                    duration=eff.duration,
                    offset_x=eff.offset_x,
                    offset_y=eff.offset_y,
                )
                seq.frames.append(frame)

                # Follow chain via next_index, or advance to next entry
                if eff.next_index > 0 and eff.next_index != current_idx:
                    current_idx = eff.next_index
                else:
                    break  # End of chain

            if seq.frames:
                sequences.append(seq)

        return sequences
