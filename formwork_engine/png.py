"""Deterministic PNG encoding and a tiny anti-aliased rasterizer for icons.

Standard library only. Output bytes depend only on the drawing calls, so icon
generation is repeatable across machines.
"""

from __future__ import annotations

import math
import struct
import zlib
from typing import Callable

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(ValueError):
    """Raised for malformed PNG input."""


def read_png_size(data: bytes) -> tuple[int, int]:
    """Return (width, height) after checking the signature and IHDR chunk."""
    if len(data) < 33 or not data.startswith(PNG_SIGNATURE):
        raise PngError("missing PNG signature")
    length, kind = struct.unpack(">I4s", data[8:16])
    if kind != b"IHDR" or length != 13:
        raise PngError("first chunk is not IHDR")
    crc = struct.unpack(">I", data[29:33])[0]
    if zlib.crc32(data[12:29]) & 0xFFFFFFFF != crc:
        raise PngError("IHDR checksum mismatch")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        raise PngError("zero dimension")
    return width, height


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Encode 8-bit RGBA rows (no interlace, filter 0) as PNG bytes."""
    if len(pixels) != width * height * 4:
        raise ValueError("pixel buffer size does not match dimensions")
    stride = width * 4
    raw = b"".join(b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


Shape = Callable[[float, float], bool]
RGBA = tuple[int, int, int, int]


class Canvas:
    """Paint shapes with 4x4 supersampling, compositing source-over."""

    SAMPLES = 4

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._pixels = [[0.0, 0.0, 0.0, 0.0] for _ in range(width * height)]

    def fill(self, shape: Shape, color: RGBA, bounds: tuple[float, float, float, float] | None = None) -> None:
        x0, y0, x1, y1 = bounds or (0, 0, self.width, self.height)
        n = self.SAMPLES
        step = 1.0 / n
        offsets = [(i + 0.5) * step for i in range(n)]
        alpha = color[3] / 255.0
        for py in range(max(0, int(math.floor(y0))), min(self.height, int(math.ceil(y1)))):
            for px in range(max(0, int(math.floor(x0))), min(self.width, int(math.ceil(x1)))):
                hits = 0
                for oy in offsets:
                    for ox in offsets:
                        if shape(px + ox, py + oy):
                            hits += 1
                if not hits:
                    continue
                coverage = alpha * hits / float(n * n)
                pixel = self._pixels[py * self.width + px]
                out_a = coverage + pixel[3] * (1 - coverage)
                for channel in range(3):
                    src = color[channel] / 255.0
                    dst = pixel[channel]
                    pixel[channel] = (
                        (src * coverage + dst * pixel[3] * (1 - coverage)) / out_a if out_a else 0.0
                    )
                pixel[3] = out_a

    def to_png(self) -> bytes:
        out = bytearray()
        for r, g, b, a in self._pixels:
            out += bytes(
                (
                    int(round(r * 255)),
                    int(round(g * 255)),
                    int(round(b * 255)),
                    int(round(a * 255)),
                )
            )
        return encode_rgba(self.width, self.height, bytes(out))


def rounded_rect(x0: float, y0: float, x1: float, y1: float, radius: float) -> Shape:
    radius = max(0.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0))

    def inside(x: float, y: float) -> bool:
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        cx = min(max(x, x0 + radius), x1 - radius)
        cy = min(max(y, y0 + radius), y1 - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius + 1e-9

    return inside


def ring(outer: Shape, inner: Shape) -> Shape:
    return lambda x, y: outer(x, y) and not inner(x, y)


def circle(cx: float, cy: float, radius: float) -> Shape:
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius


def triangle(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> Shape:
    def sign(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (p[0] - r[0]) * (q[1] - r[1]) - (q[0] - r[0]) * (p[1] - r[1])

    def inside(x: float, y: float) -> bool:
        point = (x, y)
        d1, d2, d3 = sign(point, a, b), sign(point, b, c), sign(point, c, a)
        negative = d1 < 0 or d2 < 0 or d3 < 0
        positive = d1 > 0 or d2 > 0 or d3 > 0
        return not (negative and positive)

    return inside
