"""Rendered output files and content hashing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

OWNERSHIP_MANAGED = "managed"
OWNERSHIP_SEED = "seed"
OWNERSHIPS = (OWNERSHIP_MANAGED, OWNERSHIP_SEED)
RESERVED_PREFIXES = ("firm/", ".toolkit/")


def is_reserved_path(path: str) -> bool:
    """True for paths inside the inputs or engine state folders, in any letter case.

    Windows and macOS default filesystems are case-insensitive, so ``FIRM/firm.json``
    is the same file as ``firm/firm.json``.
    """
    return path.casefold().startswith(RESERVED_PREFIXES)


@dataclass(frozen=True)
class OutputFile:
    """One file an adapter wants in the workspace."""

    path: str
    content: bytes
    adapter: str
    ownership: str = OWNERSHIP_MANAGED
    text: bool = True

    def __post_init__(self) -> None:
        if self.ownership not in OWNERSHIPS:
            raise ValueError("unknown ownership {!r}".format(self.ownership))

    @property
    def sha256(self) -> str:
        return content_hash(self.content, self.text)


def text_file(path: str, text: str, adapter: str, ownership: str = OWNERSHIP_MANAGED) -> OutputFile:
    """Build a UTF-8, LF-terminated text output."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return OutputFile(path, normalized.encode("utf-8"), adapter, ownership, True)


def binary_file(path: str, content: bytes, adapter: str) -> OutputFile:
    return OutputFile(path, content, adapter, OWNERSHIP_MANAGED, False)


def content_hash(content: bytes, text: bool) -> str:
    """SHA-256; text content is hashed with CRLF normalized to LF."""
    if text:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()
