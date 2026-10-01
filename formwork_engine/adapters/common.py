"""Always-on outputs: brand assets, fonts, notices, and firm-owned seeds."""

from __future__ import annotations

from pathlib import Path

from formwork_engine import __version__
from formwork_engine.adapters import RenderResult
from formwork_engine.adapters import layout
from formwork_engine.outputs import OWNERSHIP_SEED, binary_file, text_file
from formwork_engine.profile import Profile
from formwork_engine.textutil import md, render_file

ADAPTER_ID = "common"
LICENSE_RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "FOUNDATION_LICENSE.txt"
LUCIDE_RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "LUCIDE_LICENSE.txt"


def render(profile: Profile) -> RenderResult:
    result = RenderResult()
    config = profile.config

    for (slot, variant), entry in sorted(config.assets.items()):
        for fmt, rel in sorted(entry.items()):
            result.files.append(
                binary_file(layout.brand_path(slot, variant, fmt), profile.files[rel], ADAPTER_ID)
            )
    # Missing inverse variants fall back to the light files at the inverse path,
    # so every consumer can reference both slots unconditionally.
    for slot in ("wordmark", "symbol"):
        if (slot, "inverse") not in config.assets:
            for fmt in ("svg", "png"):
                _, content = profile.asset(slot, "light", fmt)
                result.files.append(binary_file(layout.brand_path(slot, "inverse", fmt), content, ADAPTER_ID))

    font_rows = []
    for font in config.fonts:
        for font_file in font.files:
            result.files.append(
                binary_file(layout.font_path(font, font_file), profile.files[font_file.path], ADAPTER_ID)
            )
        license_target = layout.font_license_path(font)
        result.files.append(
            text_file(license_target, profile.files[font.license_file].decode("utf-8-sig"), ADAPTER_ID)
        )
        font_rows.append(
            "| {} | {} | {} | [{}]({}) |".format(
                md(font.family), md(font.license), font.source, license_target, license_target
            )
        )

    notice_lines = []
    for rel in config.notices:
        target = "{}/{}".format(layout.BRAND_NOTICES_DIR, rel.rsplit("/", 1)[-1])
        result.files.append(text_file(target, profile.files[rel].decode("utf-8-sig"), ADAPTER_ID))
        notice_lines.append("- [{}]({})".format(target, target))

    if "ui-kit" in config.surfaces:
        lucide = LUCIDE_RESOURCE.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        icon_notices = (
            "The `ui-kit` surface packages line-icon geometry derived from Lucide "
            "(<https://lucide.dev>) in `{}/Icons.xaml`. Lucide is licensed ISC, with "
            "portions MIT from Feather; the license texts follow.\n\n```text\n{}\n```".format(
                layout.ui_kit_dir(config.technical), lucide
            )
        )
    else:
        icon_notices = "_No icon sets are packaged._"

    license_text = LICENSE_RESOURCE.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    result.files.append(
        text_file(
            layout.NOTICES_FILE,
            render_file(
                "THIRD_PARTY_NOTICES.md.tmpl",
                {
                    "foundation_version": __version__,
                    "foundation_license": license_text,
                    "font_rows": "\n".join(font_rows) if font_rows else "| _No fonts are packaged; outputs use system fonts._ | | | |",
                    "icon_notices": icon_notices,
                    "brand_notices": "\n".join(notice_lines) if notice_lines else "_This profile supplies no brand notices._",
                },
            ),
            ADAPTER_ID,
        )
    )

    result.files.append(
        text_file(layout.README_FILE, render_file("workspace-README.md.tmpl", {}), ADAPTER_ID, OWNERSHIP_SEED)
    )
    result.files.append(
        text_file(
            layout.GITATTRIBUTES_FILE,
            "* text=auto eol=lf\n*.png binary\n*.ttf binary\n*.otf binary\n",
            ADAPTER_ID,
            OWNERSHIP_SEED,
        )
    )
    return result
