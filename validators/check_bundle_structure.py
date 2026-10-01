#!/usr/bin/env python3
"""Validate pyRevit extension and executable bundle structure.

This validator deliberately uses only the Python standard library. In addition
to checking required files, it validates the small metadata surface that must
be reliable before a bundle is handed to pyRevit.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_DIR_NAME = "extensions"
REQUIRED_BUTTON_FILES = {"script.py", "bundle.yaml", "icon.png"}
REQUIRED_BUNDLE_FIELDS = {"title", "tooltip", "author"}
REQUIRED_EXTENSION_FIELDS = {"name", "author"}
EXPECTED_ICON_SIZE = (32, 32)


def parse_yaml_metadata(text: str) -> dict[str, str]:
    """Parse the flat key/value metadata used by pyRevit bundle manifests."""
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip().strip("'\"")
    return data


def read_png_size(path: Path) -> tuple[int, int]:
    """Validate a PNG chunk stream and return its dimensions."""
    data = path.read_bytes()
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("file is not a valid PNG")

    offset = 8
    dimensions: tuple[int, int] | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    interlace_method: int | None = None
    image_data_chunks: list[bytes] = []
    palette_entries = 0
    saw_end = False
    chunk_index = 0

    while offset < len(data):
        if len(data) - offset < 12:
            raise ValueError("PNG contains a truncated chunk")

        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        chunk_end = chunk_data_end + 4
        if chunk_end > len(data):
            raise ValueError("PNG contains a truncated chunk payload")

        expected_crc = struct.unpack(">I", data[chunk_data_end:chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(data[chunk_data_start:chunk_data_end], actual_crc)
        if expected_crc != (actual_crc & 0xFFFFFFFF):
            raise ValueError("PNG contains a chunk with an invalid CRC")

        if chunk_index == 0 and (chunk_type != b"IHDR" or length != 13):
            raise ValueError("PNG must begin with a 13-byte IHDR chunk")
        if chunk_type == b"IHDR":
            if dimensions is not None:
                raise ValueError("PNG contains more than one IHDR chunk")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression_method,
                filter_method,
                interlace_method,
            ) = struct.unpack(">IIBBBBB", data[chunk_data_start:chunk_data_end])
            dimensions = (width, height)
            if dimensions[0] == 0 or dimensions[1] == 0:
                raise ValueError("PNG dimensions must be greater than zero")
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if color_type not in valid_depths or bit_depth not in valid_depths[color_type]:
                raise ValueError(
                    f"PNG uses invalid bit depth {bit_depth} for color type {color_type}"
                )
            if compression_method != 0 or filter_method != 0:
                raise ValueError(
                    "PNG icon must use the standard compression and filter methods"
                )
            if interlace_method not in {0, 1}:
                raise ValueError(f"PNG uses invalid interlace method {interlace_method}")
        elif chunk_type == b"PLTE":
            if length == 0 or length > 768 or length % 3 != 0:
                raise ValueError("PNG contains an invalid palette chunk")
            palette_entries = length // 3
        elif chunk_type == b"IDAT":
            image_data_chunks.append(data[chunk_data_start:chunk_data_end])
        elif chunk_type == b"IEND":
            if length != 0:
                raise ValueError("PNG IEND chunk must be empty")
            if chunk_end != len(data):
                raise ValueError("PNG contains data after its IEND chunk")
            saw_end = True
            break

        offset = chunk_end
        chunk_index += 1

    if dimensions is None:
        raise ValueError("PNG is missing its IHDR chunk")
    if not image_data_chunks:
        raise ValueError("PNG is missing image data")
    if not saw_end:
        raise ValueError("PNG is missing its IEND chunk")
    if color_type == 3 and palette_entries == 0:
        raise ValueError("Indexed-color PNG is missing its palette")

    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(b"".join(image_data_chunks))
        decoded += decompressor.flush()
    except zlib.error as exc:
        raise ValueError(f"PNG image data is not a valid zlib stream: {exc}") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("PNG image data contains an incomplete or trailing zlib stream")

    channels_by_color_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    bits_per_pixel = channels_by_color_type[color_type] * bit_depth
    scanline_widths: list[tuple[int, int]] = []
    if interlace_method == 0:
        scanline_widths.append((dimensions[0], dimensions[1]))
    else:
        adam7_passes = (
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        )
        for start_x, start_y, step_x, step_y in adam7_passes:
            pass_width = (
                0
                if dimensions[0] <= start_x
                else (dimensions[0] - start_x + step_x - 1) // step_x
            )
            pass_height = (
                0
                if dimensions[1] <= start_y
                else (dimensions[1] - start_y + step_y - 1) // step_y
            )
            if pass_width and pass_height:
                scanline_widths.append((pass_width, pass_height))

    decoded_offset = 0
    for pass_width, pass_height in scanline_widths:
        row_data_size = (pass_width * bits_per_pixel + 7) // 8
        row_size = 1 + row_data_size
        for _ in range(pass_height):
            if decoded_offset >= len(decoded):
                raise ValueError("PNG decoded data ends before all scanlines")
            filter_type = decoded[decoded_offset]
            if filter_type > 4:
                raise ValueError(
                    f"PNG scanline at byte {decoded_offset} uses invalid filter type "
                    f"{filter_type}"
                )
            decoded_offset += row_size

    if len(decoded) != decoded_offset:
        raise ValueError(
            f"PNG decoded data is {len(decoded)} bytes; expected {decoded_offset}"
        )

    return dimensions


def validate_bundle_structure(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for all extensions below *root*."""
    errors: list[str] = []
    warnings: list[str] = []
    extension_dir = root / EXT_DIR_NAME

    if not extension_dir.is_dir():
        return (["No extensions/ directory found."], warnings)

    extensions = sorted(path for path in extension_dir.glob("*.extension") if path.is_dir())
    if not extensions:
        return (["Missing *.extension folder inside extensions/."], warnings)

    for extension in extensions:
        relative_extension = extension.relative_to(root)
        manifest_path = extension / "extension.json"
        if not manifest_path.is_file():
            errors.append(f"Missing extension.json in {relative_extension}.")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"Could not parse {manifest_path.relative_to(root)}: {exc}.")
            else:
                for field in sorted(REQUIRED_EXTENSION_FIELDS):
                    value = manifest.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"Extension manifest {manifest_path.relative_to(root)} "
                            f"is missing non-empty '{field}'."
                        )

        buttons = sorted(path for path in extension.rglob("*.pushbutton") if path.is_dir())
        if not buttons:
            warnings.append(f"No pushbuttons found in {relative_extension}.")

        for button in buttons:
            relative_button = button.relative_to(root)
            present = {path.name for path in button.iterdir() if path.is_file()}
            missing_files = sorted(REQUIRED_BUTTON_FILES - present)
            if missing_files:
                errors.append(
                    f"Button '{relative_button}' is missing required files: {missing_files}."
                )

            bundle_path = button / "bundle.yaml"
            if bundle_path.is_file():
                try:
                    metadata = parse_yaml_metadata(bundle_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError) as exc:
                    errors.append(f"Could not read {bundle_path.relative_to(root)}: {exc}.")
                else:
                    for field in sorted(REQUIRED_BUNDLE_FIELDS):
                        if not metadata.get(field, "").strip():
                            errors.append(
                                f"Bundle metadata {bundle_path.relative_to(root)} "
                                f"is missing non-empty '{field}'."
                            )

            icon_path = button / "icon.png"
            if icon_path.is_file():
                try:
                    dimensions = read_png_size(icon_path)
                except (OSError, ValueError, struct.error) as exc:
                    errors.append(f"Invalid icon {icon_path.relative_to(root)}: {exc}.")
                else:
                    if dimensions != EXPECTED_ICON_SIZE:
                        errors.append(
                            f"Icon {icon_path.relative_to(root)} is {dimensions[0]}x{dimensions[1]}; "
                            f"expected {EXPECTED_ICON_SIZE[0]}x{EXPECTED_ICON_SIZE[1]}."
                        )

    return errors, warnings


def main() -> None:
    errors, warnings = validate_bundle_structure()
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print("ERROR: Bundle structure validation failed:")
        for error in errors:
            print(f" - {error}")
        sys.exit(1)

    print("OK: Bundle structures and metadata are valid.")


if __name__ == "__main__":
    main()
