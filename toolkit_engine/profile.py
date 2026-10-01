"""Load a firm configuration directory into a validated, resolved Profile."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ElementTree

from toolkit_engine.config import ASSET_SLOTS, FirmConfig, validate_config
from toolkit_engine.diagnostics import Diagnostics
from toolkit_engine.jsonio import JsonInputError, loads_strict
from toolkit_engine.png import PngError, read_png_size
from toolkit_engine.tokens import STATUS_NAMES, TokenSet, check_required_roles, contrast_ratio, parse_tokens

CONFIG_FILE = "firm.json"
MAX_INPUT_BYTES = 8 * 1024 * 1024
SYSTEM_FONTS = frozenset(
    {
        "arial",
        "arial narrow",
        "calibri",
        "cambria",
        "cascadia code",
        "cascadia mono",
        "consolas",
        "georgia",
        "segoe ui",
        "tahoma",
        "times new roman",
        "trebuchet ms",
        "verdana",
    }
)
GENERIC_FAMILIES = frozenset({"serif", "sans-serif", "monospace", "system-ui", "ui-monospace", "cursive"})
EXTERNAL_REFERENCE = re.compile(r"(?:https?:)?//|javascript:|data:", re.IGNORECASE)


@dataclass(frozen=True)
class Profile:
    """Validated inputs. ``files`` holds every referenced input file's bytes."""

    root: Path
    config: FirmConfig
    tokens: TokenSet
    files: dict[str, bytes]
    inputs_sha256: str

    def asset(self, slot: str, variant: str, fmt: str) -> tuple[str, bytes]:
        entry = self.config.assets.get((slot, variant)) or self.config.assets[(slot, "light")]
        path = entry[fmt]
        return path, self.files[path]

    @property
    def packaged_families(self) -> frozenset[str]:
        return frozenset(font.family for font in self.config.fonts)


def load_profile(firm_dir: Path, diags: Diagnostics) -> Profile | None:
    """Validate *firm_dir* (containing firm.json). Returns None on errors."""
    config_path = firm_dir / CONFIG_FILE
    if not config_path.is_file():
        diags.error(
            "config.not-found",
            CONFIG_FILE,
            "No firm.json found in the firm configuration directory.",
            "Point at the folder that contains firm.json (in a workspace, its firm/ folder).",
        )
        return None
    files: dict[str, bytes] = {}
    raw_config = _read_input(firm_dir, CONFIG_FILE, diags)
    if raw_config is None:
        return None
    files[CONFIG_FILE] = raw_config
    try:
        data = loads_strict(raw_config.decode("utf-8-sig"))
    except (JsonInputError, UnicodeDecodeError) as exc:
        diags.error("config.json-invalid", CONFIG_FILE, str(exc))
        return None
    config = validate_config(data, CONFIG_FILE, diags)
    if config is None:
        return None

    raw_tokens = _read_input(firm_dir, config.tokens_path, diags)
    if raw_tokens is None:
        return None
    files[config.tokens_path] = raw_tokens
    try:
        token_doc = loads_strict(raw_tokens.decode("utf-8-sig"))
    except (JsonInputError, UnicodeDecodeError) as exc:
        diags.error("token.json-invalid", config.tokens_path, str(exc))
        return None
    tokens = parse_tokens(token_doc, config.tokens_path, diags)
    if tokens is None:
        return None
    check_required_roles(tokens, config.tokens_path, diags)

    for slot in ASSET_SLOTS:
        if (slot, "light") not in config.assets:
            diags.error(
                "brand.asset-missing",
                "{}#/brand/assets/{}/light".format(CONFIG_FILE, slot),
                "The {} slot needs a light variant with svg and png files.".format(slot),
            )
        elif (slot, "inverse") not in config.assets:
            diags.warning(
                "brand.inverse-fallback",
                "{}#/brand/assets/{}".format(CONFIG_FILE, slot),
                "No inverse {}; the light variant will be used on dark surfaces.".format(slot),
                "Supply a separately drawn inverse file for dark/brand backgrounds.",
            )
    for (slot, variant), entry in sorted(config.assets.items()):
        for fmt, rel in sorted(entry.items()):
            content = _read_input(firm_dir, rel, diags)
            if content is None:
                continue
            files[rel] = content
            if fmt == "svg":
                _check_svg(rel, content, diags)
            else:
                try:
                    read_png_size(content)
                except PngError as exc:
                    diags.error("brand.png-invalid", rel, "Not a valid PNG: {}.".format(exc))

    for font in config.fonts:
        for font_file in font.files:
            rel = font_file.path
            content = _read_input(firm_dir, rel, diags)
            if content is None:
                continue
            files[rel] = content
            if content[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                diags.error("font.file-invalid", rel, "File is not a TrueType/OpenType font.")
        content = _read_input(firm_dir, font.license_file, diags)
        if content is not None:
            files[font.license_file] = content
    for rel in config.notices:
        content = _read_input(firm_dir, rel, diags)
        if content is not None:
            files[rel] = content

    if diags.has_errors:
        return None
    _check_fonts(config, tokens, diags)
    _check_contrast(tokens, config.tokens_path, diags)

    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(files[rel]).digest())
    return Profile(firm_dir, config, tokens, files, digest.hexdigest())


def _read_input(firm_dir: Path, rel: str, diags: Diagnostics) -> bytes | None:
    from toolkit_engine.paths import UnsafePathError, guard_target

    try:
        path = guard_target(firm_dir, rel)
    except UnsafePathError as exc:
        diags.error(exc.code, rel, str(exc))
        return None
    if not path.is_file():
        diags.error("input.missing", rel, "Referenced file does not exist.")
        return None
    if path.stat().st_size > MAX_INPUT_BYTES:
        diags.error("input.too-large", rel, "Input files are limited to {} MiB.".format(MAX_INPUT_BYTES // 1048576))
        return None
    return path.read_bytes()


def _check_svg(rel: str, content: bytes, diags: Diagnostics) -> None:
    text = content.decode("utf-8", errors="replace")
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        diags.error("brand.svg-unsafe", rel, "SVG must not declare a DOCTYPE or entities.")
        return
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        diags.error("brand.svg-invalid", rel, "SVG is not well-formed XML: {}.".format(exc))
        return
    if not root.tag.endswith("svg"):
        diags.error("brand.svg-invalid", rel, "Root element is not <svg>.")
        return
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in ("script", "foreignObject", "iframe", "image"):
            diags.error("brand.svg-unsafe", rel, "SVG contains a <{}> element.".format(local))
            return
        for name, value in element.attrib.items():
            attr = name.rsplit("}", 1)[-1]
            if attr.lower().startswith("on"):
                diags.error("brand.svg-unsafe", rel, "SVG contains an event-handler attribute.")
                return
            if attr == "href" and not value.startswith("#"):
                diags.error("brand.svg-external", rel, "SVG references an external resource.")
                return
            if attr == "style" and EXTERNAL_REFERENCE.search(value):
                diags.error("brand.svg-external", rel, "SVG style references an external resource.")
                return
        if local == "metadata" and len(list(element)):
            diags.warning(
                "brand.svg-metadata",
                rel,
                "SVG carries embedded metadata, which will be published with every generated workspace.",
                "Remove <metadata> unless it is intentional provenance.",
            )


def _check_fonts(config: FirmConfig, tokens: TokenSet, diags: Diagnostics) -> None:
    packaged = {font.family.casefold() for font in config.fonts}
    for role in ("display", "body", "label", "code"):
        stack = tokens.value("font." + role)
        primary = stack[0]
        key = primary.casefold()
        if key in packaged or key in GENERIC_FAMILIES:
            continue
        if key in SYSTEM_FONTS:
            diags.info(
                "font.system",
                "{}#/font/{}".format(config.tokens_path, role),
                "{!r} is a common system font and is not packaged.".format(primary),
            )
        else:
            diags.warning(
                "font.not-packaged",
                "{}#/font/{}".format(config.tokens_path, role),
                "{!r} is not packaged; outputs fall back to {}.".format(primary, ", ".join(stack[1:]) or "the platform default"),
                "Add the font files and licence under brand.fonts, or choose a packaged family.",
            )


def _check_contrast(tokens: TokenSet, source: str, diags: Diagnostics) -> None:
    pairs = [
        ("color.text.primary", "color.surface.default", 4.5),
        ("color.text.secondary", "color.surface.default", 4.5),
        ("color.text.primary", "color.surface.card", 4.5),
        ("color.text.inverse", "color.surface.inverse", 4.5),
        ("color.action.primary.fg", "color.action.primary.bg", 4.5),
        ("color.action.secondary.fg", "color.action.secondary.bg", 4.5),
        ("color.focus.ring", "color.surface.default", 3.0),
    ]
    pairs += [("color.status.{}.fg".format(s), "color.status.{}.bg".format(s), 4.5) for s in STATUS_NAMES]
    for fg, bg, minimum in pairs:
        ratio = contrast_ratio(tokens.color(fg), tokens.color(bg))
        if ratio < minimum:
            diags.warning(
                "a11y.contrast",
                source,
                "{} on {} has contrast {:.2f}:1 (minimum {}:1).".format(fg, bg, ratio, minimum),
                "Darken the foreground or lighten the background.",
            )

