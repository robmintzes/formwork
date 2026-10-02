"""Firm configuration (firm.json) v1 validation.

The engine is the authority for the contract in FOUNDATION_SPEC section 2;
schemas/firm-config.v1.schema.json mirrors it for editor completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from formwork_engine import CONFIG_SCHEMA_VERSION, __version__
from formwork_engine.diagnostics import Diagnostics, did_you_mean
from formwork_engine.paths import check_relative_path, is_reserved_name

SURFACES = ("pyrevit-sample", "wpf-specimen", "html-guide", "governance", "mcp-bridge", "ui-kit", "web-host", "array-along-path", "revit-addin", "python-app", "web-app")
# Surfaces that only make sense inside another surface's output.
SURFACE_REQUIRES = {"mcp-bridge": ("pyrevit-sample",), "ui-kit": ("pyrevit-sample",), "web-host": ("pyrevit-sample",), "array-along-path": ("pyrevit-sample", "web-host", "ui-kit")}
ASSET_SLOTS = ("wordmark", "symbol")
ASSET_VARIANTS = ("light", "inverse")
ASSET_FORMATS = ("svg", "png")
REDISTRIBUTABLE_FONT_LICENSES = ("OFL-1.1", "Apache-2.0", "MIT")
APPEARANCE_CHOICES: dict[str, dict[str, tuple[str, ...]]] = {
    "button": {
        "primary": ("solid", "outline"),
        "secondary": ("outline", "tonal", "ghost"),
        "shape": ("square", "rounded", "pill"),
        "label_case": ("as-written", "uppercase"),
    },
    "badge": {
        "style": ("soft", "solid", "outline"),
        "shape": ("square", "rounded", "pill"),
        "label_case": ("as-written", "uppercase"),
    },
}

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAMESPACE = re.compile(r"^[a-z][a-z0-9]{1,23}$")
EXTENSION_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,39}$")
FOLDER_TITLE = re.compile(r"^[A-Za-z0-9]+(?: [A-Za-z0-9]+)*$")
BRANCH_COMPONENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HTTPS_URL = re.compile(r"^https://[^\s<>\"'`]+$")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Identity:
    display_name: str
    short_name: str
    author: str
    logo_alt: str
    support_url: str
    documentation_url: str | None


@dataclass(frozen=True)
class Technical:
    namespace: str
    workspace_id: str
    extension: str
    tab: str
    sample_panel: str


@dataclass(frozen=True)
class FontFile:
    path: str
    weight: int
    style: str


@dataclass(frozen=True)
class FontSpec:
    family: str
    files: tuple[FontFile, ...]
    license: str
    license_file: str
    source: str


@dataclass(frozen=True)
class Appearance:
    button_primary: str
    button_secondary: str
    button_shape: str
    button_label_case: str
    badge_style: str
    badge_shape: str
    badge_label_case: str
    registration_marks: bool


@dataclass(frozen=True)
class Maintainer:
    name: str
    branch_prefix: str


@dataclass(frozen=True)
class Governance:
    required_approvals: int
    approvals_defaulted: bool


@dataclass(frozen=True)
class FirmConfig:
    schema_version: int
    profile_id: str
    description: str
    fictional: bool
    identity: Identity
    technical: Technical
    tokens_path: str
    assets: dict[tuple[str, str], dict[str, str]]
    fonts: tuple[FontSpec, ...]
    notices: tuple[str, ...]
    appearance: Appearance
    surfaces: tuple[str, ...]
    maintainers: tuple[Maintainer, ...]
    governance: Governance = Governance(0, True)
    extensions: dict[str, Any] = field(default_factory=dict)


class _Reader:
    """Typed accessors that record diagnostics instead of raising."""

    def __init__(self, source: str, diags: Diagnostics) -> None:
        self.source = source
        self.diags = diags

    def loc(self, pointer: str) -> str:
        return "{}#{}".format(self.source, pointer)

    def obj(
        self,
        value: Any,
        pointer: str,
        required: tuple[str, ...],
        optional: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.diags.error("config.type", self.loc(pointer), "Expected an object.")
            return None
        allowed = required + optional
        for key in value:
            if key.startswith("x-"):
                continue
            if key not in allowed:
                self.diags.error(
                    "config.unknown-field",
                    self.loc(pointer + "/" + key),
                    "Unknown field {!r}.".format(key),
                    did_you_mean(key, allowed) or "Prefix firm-specific data with 'x-'.",
                )
        for key in required:
            if key not in value:
                self.diags.error(
                    "config.missing-field",
                    self.loc(pointer + "/" + key),
                    "Required field {!r} is missing.".format(key),
                )
        return value

    def text(
        self,
        container: dict[str, Any],
        key: str,
        pointer: str,
        *,
        max_length: int,
        pattern: re.Pattern[str] | None = None,
        rule: str = "",
        required: bool = True,
    ) -> str | None:
        if key not in container:
            return None if not required else None
        value = container[key]
        location = self.loc(pointer + "/" + key)
        if not isinstance(value, str) or not value.strip():
            self.diags.error("config.type", location, "Expected a non-empty string.")
            return None
        if value != value.strip() or CONTROL_CHARS.search(value):
            self.diags.error(
                "config.text-invalid",
                location,
                "Text must not have leading/trailing whitespace or control characters.",
            )
            return None
        if len(value) > max_length:
            self.diags.error(
                "config.text-too-long", location, "Maximum length is {} characters.".format(max_length)
            )
            return None
        if pattern is not None and not pattern.fullmatch(value):
            self.diags.error("config.text-invalid", location, "Value {!r} must be {}.".format(value, rule))
            return None
        return value

    def choice(self, container: dict[str, Any], key: str, pointer: str, options: tuple[str, ...]) -> str | None:
        if key not in container:
            return None
        value = container[key]
        if value not in options:
            self.diags.error(
                "config.choice-invalid",
                self.loc(pointer + "/" + key),
                "{!r} is not one of {}.".format(value, ", ".join(options)),
                did_you_mean(str(value), options),
            )
            return None
        return value

    def relpath(self, value: Any, pointer: str) -> str | None:
        location = self.loc(pointer)
        if not isinstance(value, str):
            self.diags.error("config.type", location, "Expected a relative path string.")
            return None
        problem = check_relative_path(value)
        if problem:
            self.diags.error("config.path-invalid", location, "Path {!r} {}.".format(value, problem))
            return None
        return value


def validate_config(data: Any, source: str, diags: Diagnostics) -> FirmConfig | None:
    """Validate a parsed firm.json document."""
    r = _Reader(source, diags)
    errors_before = len([d for d in diags.items if d.severity == "error"])

    if not isinstance(data, dict):
        diags.error("config.type", source, "firm.json must contain a JSON object.")
        return None
    version = data.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        diags.error(
            "config.schema-version-missing",
            r.loc("/schema_version"),
            "schema_version must be an integer.",
            "This foundation reads schema_version {}.".format(CONFIG_SCHEMA_VERSION),
        )
        return None
    if version > CONFIG_SCHEMA_VERSION:
        diags.error(
            "config.schema-too-new",
            r.loc("/schema_version"),
            "Configuration schema {} is newer than this foundation ({}) supports.".format(
                version, __version__
            ),
            "Upgrade the foundation; this one reads schema_version {}.".format(CONFIG_SCHEMA_VERSION),
        )
        return None
    if version < 1:
        diags.error("config.schema-version-invalid", r.loc("/schema_version"), "schema_version must be >= 1.")
        return None

    top = r.obj(
        data,
        "",
        ("schema_version", "profile", "identity", "technical", "brand", "appearance", "surfaces", "maintainers"),
        ("$schema", "governance"),  # $schema: editor hint for schemas/firm-config.v1.schema.json
    )
    if top is None:
        return None

    profile = r.obj(top.get("profile", {}), "/profile", ("id", "description"), ("fictional",)) or {}
    profile_id = r.text(profile, "id", "/profile", max_length=40, pattern=KEBAB, rule="lowercase kebab-case")
    description = r.text(profile, "description", "/profile", max_length=400)
    fictional = profile.get("fictional", False)
    if not isinstance(fictional, bool):
        diags.error("config.type", r.loc("/profile/fictional"), "Expected true or false.")

    identity = _identity(r, top.get("identity", {}))
    technical = _technical(r, top.get("technical", {}))
    brand = _brand(r, top.get("brand", {}))
    appearance = _appearance(r, top.get("appearance", {}))
    surfaces = _surfaces(r, top.get("surfaces"))
    maintainers = _maintainers(r, top.get("maintainers"))
    governance = _governance(r, top.get("governance"), len(maintainers))

    errors_after = len([d for d in diags.items if d.severity == "error"])
    if errors_after > errors_before:
        return None
    assert identity and technical and brand and appearance and profile_id and description
    tokens_path, assets, fonts, notices = brand
    return FirmConfig(
        schema_version=version,
        profile_id=profile_id,
        description=description,
        fictional=bool(fictional),
        identity=identity,
        technical=technical,
        tokens_path=tokens_path,
        assets=assets,
        fonts=fonts,
        notices=notices,
        appearance=appearance,
        surfaces=surfaces,
        maintainers=maintainers,
        governance=governance,
        extensions={k: v for k, v in top.items() if k.startswith("x-")},
    )


def _identity(r: _Reader, value: Any) -> Identity | None:
    obj = r.obj(value, "/identity", ("display_name", "short_name", "author", "logo_alt", "links"))
    if obj is None:
        return None
    p = "/identity"
    display_name = r.text(obj, "display_name", p, max_length=80)
    short_name = r.text(obj, "short_name", p, max_length=24)
    author = r.text(obj, "author", p, max_length=80)
    logo_alt = r.text(obj, "logo_alt", p, max_length=80)
    links = r.obj(obj.get("links", {}), p + "/links", ("support",), ("documentation",)) or {}
    support = r.text(links, "support", p + "/links", max_length=300, pattern=HTTPS_URL, rule="an https:// URL")
    documentation = r.text(
        links, "documentation", p + "/links", max_length=300, pattern=HTTPS_URL, rule="an https:// URL", required=False
    )
    if None in (display_name, short_name, author, logo_alt, support):
        return None
    return Identity(display_name, short_name, author, logo_alt, support, documentation)  # type: ignore[arg-type]


def _folder_title(r: _Reader, obj: dict[str, Any], key: str, pointer: str) -> str | None:
    value = r.text(obj, key, pointer, max_length=40, pattern=FOLDER_TITLE, rule="letters and digits separated by single spaces")
    if value is not None and (is_reserved_name(value) or value.lower() == "placeholder"):
        r.diags.error(
            "config.name-reserved",
            r.loc(pointer + "/" + key),
            "{!r} is reserved (Windows device name or template placeholder).".format(value),
        )
        return None
    return value


def _technical(r: _Reader, value: Any) -> Technical | None:
    obj = r.obj(value, "/technical", ("namespace", "workspace_id", "pyrevit"))
    if obj is None:
        return None
    p = "/technical"
    namespace = r.text(obj, "namespace", p, max_length=24, pattern=NAMESPACE, rule="2-24 lowercase letters/digits starting with a letter")
    workspace_id = r.text(obj, "workspace_id", p, max_length=64, pattern=KEBAB, rule="lowercase kebab-case")
    pyrevit = r.obj(obj.get("pyrevit", {}), p + "/pyrevit", ("extension", "tab", "sample_panel")) or {}
    extension = r.text(pyrevit, "extension", p + "/pyrevit", max_length=40, pattern=EXTENSION_NAME, rule="letters and digits starting with a letter")
    if extension is not None and (is_reserved_name(extension) or extension.lower() == "placeholder"):
        r.diags.error("config.name-reserved", r.loc(p + "/pyrevit/extension"), "{!r} is reserved.".format(extension))
        extension = None
    tab = _folder_title(r, pyrevit, "tab", p + "/pyrevit")
    sample_panel = _folder_title(r, pyrevit, "sample_panel", p + "/pyrevit")
    if None in (namespace, workspace_id, extension, tab, sample_panel):
        return None
    return Technical(namespace, workspace_id, extension, tab, sample_panel)  # type: ignore[arg-type]


def _brand(r: _Reader, value: Any) -> tuple[str, dict[tuple[str, str], dict[str, str]], tuple[FontSpec, ...], tuple[str, ...]] | None:
    obj = r.obj(value, "/brand", ("tokens", "assets", "fonts"), ("notices",))
    if obj is None:
        return None
    p = "/brand"
    tokens_path = r.relpath(obj.get("tokens"), p + "/tokens") if "tokens" in obj else None
    if tokens_path is not None and not tokens_path.endswith(".tokens.json"):
        r.diags.error("config.path-invalid", r.loc(p + "/tokens"), "Token files must end in .tokens.json.")
        tokens_path = None

    assets: dict[tuple[str, str], dict[str, str]] = {}
    asset_obj = r.obj(obj.get("assets", {}), p + "/assets", ASSET_SLOTS) or {}
    for slot in ASSET_SLOTS:
        if slot not in asset_obj:
            continue
        slot_obj = r.obj(asset_obj[slot], "{}/assets/{}".format(p, slot), ("light",), ("inverse",)) or {}
        for variant in ASSET_VARIANTS:
            if variant not in slot_obj:
                continue
            pointer = "{}/assets/{}/{}".format(p, slot, variant)
            files = r.obj(slot_obj[variant], pointer, ASSET_FORMATS) or {}
            entry: dict[str, str] = {}
            for fmt in ASSET_FORMATS:
                if fmt in files:
                    path = r.relpath(files[fmt], pointer + "/" + fmt)
                    if path is not None and not path.lower().endswith("." + fmt):
                        r.diags.error("config.path-invalid", r.loc(pointer + "/" + fmt), "Expected a .{} file.".format(fmt))
                    elif path is not None:
                        entry[fmt] = path
            if len(entry) == len(ASSET_FORMATS):
                assets[(slot, variant)] = entry

    fonts: list[FontSpec] = []
    font_list = obj.get("fonts", [])
    if not isinstance(font_list, list):
        r.diags.error("config.type", r.loc(p + "/fonts"), "Expected a list (may be empty).")
        font_list = []
    for index, font in enumerate(font_list):
        pointer = "{}/fonts/{}".format(p, index)
        f = r.obj(font, pointer, ("family", "files", "license", "license_file", "source"))
        if f is None:
            continue
        family = r.text(f, "family", pointer, max_length=60)
        license_id = r.text(f, "license", pointer, max_length=40)
        license_file = r.relpath(f.get("license_file"), pointer + "/license_file") if "license_file" in f else None
        source = r.text(f, "source", pointer, max_length=300, pattern=HTTPS_URL, rule="an https:// URL")
        files_value = f.get("files")
        font_files: list[FontFile] = []
        if not isinstance(files_value, list) or not files_value:
            r.diags.error("config.type", r.loc(pointer + "/files"), "Expected a non-empty list of font files.")
        else:
            for file_index, item in enumerate(files_value):
                file_pointer = "{}/files/{}".format(pointer, file_index)
                entry = r.obj(item, file_pointer, ("path", "weight"), ("style",))
                if entry is None or "path" not in entry:
                    continue
                path = r.relpath(entry["path"], file_pointer + "/path")
                weight = entry.get("weight")
                style = entry.get("style", "normal")
                if path is not None and not path.lower().endswith((".ttf", ".otf")):
                    r.diags.error("config.path-invalid", r.loc(file_pointer + "/path"), "Font files must be .ttf or .otf.")
                    path = None
                if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 1000:
                    r.diags.error("config.type", r.loc(file_pointer + "/weight"), "weight must be an integer 1-1000.")
                    weight = None
                if style not in ("normal", "italic"):
                    r.diags.error("config.choice-invalid", r.loc(file_pointer + "/style"), "style must be normal or italic.")
                    style = None
                if path is not None and weight is not None and style is not None:
                    font_files.append(FontFile(path, weight, style))
        if license_id is not None and license_id not in REDISTRIBUTABLE_FONT_LICENSES:
            r.diags.warning(
                "font.license-unrecognized",
                r.loc(pointer + "/license"),
                "License {!r} is not on the known-redistributable list ({}).".format(
                    license_id, ", ".join(REDISTRIBUTABLE_FONT_LICENSES)
                ),
                "Confirm the firm may copy these files into every workspace and repository it publishes.",
            )
        if family and license_id and license_file and source and font_files:
            fonts.append(FontSpec(family, tuple(font_files), license_id, license_file, source))

    notices: list[str] = []
    notice_list = obj.get("notices", [])
    if not isinstance(notice_list, list):
        r.diags.error("config.type", r.loc(p + "/notices"), "Expected a list of notice files.")
        notice_list = []
    for index, item in enumerate(notice_list):
        path = r.relpath(item, "{}/notices/{}".format(p, index))
        if path is not None:
            notices.append(path)

    if tokens_path is None:
        return None
    return tokens_path, assets, tuple(fonts), tuple(notices)


def _appearance(r: _Reader, value: Any) -> Appearance | None:
    obj = r.obj(value, "/appearance", ("button", "badge", "decorations"))
    if obj is None:
        return None
    picked: dict[str, str | None] = {}
    for group, choices in APPEARANCE_CHOICES.items():
        pointer = "/appearance/" + group
        group_obj = r.obj(obj.get(group, {}), pointer, tuple(choices)) or {}
        for key, options in choices.items():
            picked[group + "_" + key] = r.choice(group_obj, key, pointer, options)
    decorations = r.obj(obj.get("decorations", {}), "/appearance/decorations", ("registration_marks",)) or {}
    marks = decorations.get("registration_marks")
    if "registration_marks" in decorations and not isinstance(marks, bool):
        r.diags.error("config.type", r.loc("/appearance/decorations/registration_marks"), "Expected true or false.")
        marks = None
    if None in picked.values() or not isinstance(marks, bool):
        return None
    return Appearance(registration_marks=marks, **picked)  # type: ignore[arg-type]


def _surfaces(r: _Reader, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        r.diags.error("config.type", r.loc("/surfaces"), "Expected a non-empty list of surface ids.")
        return ()
    result: list[str] = []
    for index, item in enumerate(value):
        if item not in SURFACES:
            r.diags.error(
                "config.surface-unknown",
                r.loc("/surfaces/{}".format(index)),
                "Unknown surface {!r}.".format(item),
                did_you_mean(str(item), SURFACES) or "Known surfaces: {}.".format(", ".join(SURFACES)),
            )
        elif item in result:
            r.diags.error("config.surface-duplicate", r.loc("/surfaces/{}".format(index)), "Surface listed twice.")
        else:
            result.append(item)
    for surface, needed in SURFACE_REQUIRES.items():
        if surface in result:
            for dependency in needed:
                if dependency not in result:
                    r.diags.error(
                        "config.surface-requires",
                        r.loc("/surfaces"),
                        "Surface {!r} requires {!r}.".format(surface, dependency),
                        "Add {!r} to surfaces: {} extends the extension that surface generates.".format(dependency, surface),
                    )
    return tuple(result)


def _maintainers(r: _Reader, value: Any) -> tuple[Maintainer, ...]:
    if not isinstance(value, list) or not value:
        r.diags.error(
            "config.maintainers-missing",
            r.loc("/maintainers"),
            "At least one human maintainer is required.",
            "Each maintainer's branch_prefix becomes the owner prefix for task branches.",
        )
        return ()
    result: list[Maintainer] = []
    for index, item in enumerate(value):
        pointer = "/maintainers/{}".format(index)
        obj = r.obj(item, pointer, ("name", "branch_prefix"))
        if obj is None:
            continue
        name = r.text(obj, "name", pointer, max_length=80)
        prefix = r.text(
            obj, "branch_prefix", pointer, max_length=39, pattern=BRANCH_COMPONENT, rule="lowercase letters/digits with single hyphens"
        )
        if prefix in ("claude", "codex", "copilot", "gemini", "cursor", "openai", "anthropic"):
            r.diags.error("config.branch-prefix-agent", r.loc(pointer + "/branch_prefix"), "Branch prefixes name accountable humans, not AI agents.")
            prefix = None
        if name and prefix:
            result.append(Maintainer(name, prefix))
    return tuple(result)


def _governance(r: _Reader, value: Any, maintainer_count: int) -> Governance:
    """Review policy. Default: no required approval for a solo maintainer, one otherwise."""
    default = 0 if maintainer_count <= 1 else 1
    if value is None:
        return Governance(default, True)
    obj = r.obj(value, "/governance", (), ("required_approvals",)) or {}
    approvals = obj.get("required_approvals", default)
    if not isinstance(approvals, int) or isinstance(approvals, bool) or not 0 <= approvals <= 6:
        r.diags.error("config.type", r.loc("/governance/required_approvals"), "required_approvals must be an integer 0-6.")
        return Governance(default, True)
    if approvals >= maintainer_count and approvals > 0:
        r.diags.warning(
            "governance.approvals-unreachable",
            r.loc("/governance/required_approvals"),
            "{} required approval(s) with {} maintainer(s): authors cannot approve their own PRs, so merges may be impossible.".format(
                approvals, maintainer_count
            ),
            "List the other reviewers as maintainers or lower required_approvals.",
        )
    return Governance(approvals, "required_approvals" not in obj)
